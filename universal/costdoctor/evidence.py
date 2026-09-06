from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .adapters import build_adapter
from .canonical import parse_time, sha256_json, utc_now
from .registry import ModelRegistry, ProviderRegistry
from .schema import SchemaError, reject_sensitive_payload, validate_usage_event


class EvidenceError(ValueError):
    pass


def load_json_or_jsonl(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        result = [json.loads(line) for line in raw.splitlines() if line.strip()]
    else:
        payload = json.loads(raw)
        result = payload if isinstance(payload, list) else payload.get("events", [])
    if not isinstance(result, list) or not all(isinstance(item, dict) for item in result):
        raise EvidenceError("USAGE_IMPORT_FORMAT_INVALID")
    return result


class UsageImporter:
    def __init__(self, model_registry: ModelRegistry, provider_registry: ProviderRegistry):
        self.model_registry = model_registry
        self.provider_registry = provider_registry

    def normalize_records(self, records: Iterable[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
        events: list[dict[str, Any]] = []
        receipts: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        last_sequence = -1
        previous_digest: str | None = None
        provider_name = str(context.get("provider", "generic"))
        provider_config = self.provider_registry.resolve(provider_name)
        adapter = build_adapter(str(provider_config.get("adapter", "generic_v1")), provider_config)
        for raw in records:
            reject_sensitive_payload(raw)
            event = adapter.normalize(raw, context)
            event_id = event["event_id"]
            if event_id in seen_ids:
                raise EvidenceError("DUPLICATE_EVENT_REJECTED")
            if event["sequence"] <= last_sequence:
                raise EvidenceError("OUT_OF_ORDER_EVENT_REJECTED")
            if parse_time(event["ended_at"]) < parse_time(event["started_at"]):
                raise EvidenceError("EVENT_TIME_ORDER_INVALID")
            canonical_model = self.model_registry.canonical_id(event["model"])
            event["model"] = canonical_model
            event["model_registry_status"] = (self.model_registry.resolve(canonical_model) or {}).get("status", "unknown")
            validate_usage_event(event)
            digest = sha256_json(event)
            receipts.append(
                {
                    "schema": "costdoctor.append-only-receipt.v1",
                    "event_id": event_id,
                    "event_digest": digest,
                    "previous_receipt_digest": previous_digest,
                }
            )
            previous_digest = sha256_json(receipts[-1])
            event["event_digest"] = digest
            events.append(event)
            seen_ids.add(event_id)
            last_sequence = event["sequence"]
        return {
            "schema": "costdoctor.usage-evidence.v1",
            "created_at": utc_now(),
            "events": events,
            "receipts": receipts,
            "receipt_chain_head": previous_digest,
            "privacy": {
                "prompt_or_response_stored": False,
                "secret_stored": False,
                "filenames_output": False,
            },
            "adapter_health": adapter.health_check(),
        }


def verify_receipt_chain(evidence: dict[str, Any]) -> bool:
    previous: str | None = None
    events = {event["event_id"]: event for event in evidence.get("events", [])}
    for receipt in evidence.get("receipts", []):
        if receipt.get("previous_receipt_digest") != previous:
            return False
        event = dict(events.get(receipt.get("event_id"), {}))
        event.pop("event_digest", None)
        if not event or sha256_json(event) != receipt.get("event_digest"):
            return False
        previous = sha256_json(receipt)
    return previous == evidence.get("receipt_chain_head")
