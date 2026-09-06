from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .canonical import parse_time, sha256_json


class RegistryError(ValueError):
    pass


def _load_rows(directory: Path, expected_prefix: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    rows: list[dict[str, Any]] = []
    sources: list[dict[str, str]] = []
    for path in sorted(directory.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        schema = str(payload.get("schema", ""))
        if not schema.startswith(expected_prefix):
            raise RegistryError("REGISTRY_SCHEMA_INVALID")
        file_rows = payload.get("rows")
        if not isinstance(file_rows, list):
            raise RegistryError("REGISTRY_ROWS_INVALID")
        rows.extend(file_rows)
        sources.append({"name": path.name, "digest": sha256_json(payload)})
    if not sources:
        raise RegistryError("REGISTRY_EMPTY")
    return rows, sources


class ModelRegistry:
    def __init__(self, directory: Path):
        rows, sources = _load_rows(directory, "costdoctor.model-registry.")
        self.sources = sources
        self.rows: dict[str, dict[str, Any]] = {}
        self.aliases: dict[str, str] = {}
        for row in rows:
            model_id = str(row.get("canonical_id", "")).strip()
            if not model_id or model_id in self.rows:
                raise RegistryError("MODEL_ID_INVALID_OR_DUPLICATE")
            if row.get("status") not in {"active", "preview", "deprecated", "retired", "unknown"}:
                raise RegistryError("MODEL_STATUS_INVALID")
            self.rows[model_id] = dict(row)
            for alias in [model_id, *row.get("aliases", [])]:
                alias = str(alias).strip()
                if not alias or (alias in self.aliases and self.aliases[alias] != model_id):
                    raise RegistryError("MODEL_ALIAS_INVALID_OR_DUPLICATE")
                self.aliases[alias] = model_id
        self.snapshot = {"sources": sources, "digest": sha256_json(rows)}

    def resolve(self, model_or_alias: str) -> dict[str, Any] | None:
        canonical = self.aliases.get(model_or_alias)
        return dict(self.rows[canonical]) if canonical else None

    def canonical_id(self, model_or_alias: str) -> str:
        row = self.resolve(model_or_alias)
        return str(row["canonical_id"]) if row else model_or_alias

    def active_rows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.rows.values() if row["status"] in {"active", "preview"}]


class ProviderRegistry:
    def __init__(self, directory: Path):
        rows, sources = _load_rows(directory, "costdoctor.provider-registry.")
        self.rows: dict[str, dict[str, Any]] = {}
        for row in rows:
            provider = str(row.get("provider", "")).strip()
            if not provider or provider in self.rows or not row.get("adapter"):
                raise RegistryError("PROVIDER_ROW_INVALID_OR_DUPLICATE")
            self.rows[provider] = dict(row)
        self.sources = sources
        self.snapshot = {"sources": sources, "digest": sha256_json(rows)}

    def resolve(self, provider: str) -> dict[str, Any]:
        return dict(self.rows.get(provider) or self.rows.get("generic") or {})


class PricingRegistry:
    def __init__(self, directory: Path):
        rows, sources = _load_rows(directory, "costdoctor.pricing-registry.")
        self.rows = [dict(row) for row in rows]
        self.sources = sources
        self.snapshot = {"sources": sources, "digest": sha256_json(rows)}
        identities: set[tuple[str, str, str]] = set()
        for row in self.rows:
            identity = (str(row.get("provider")), str(row.get("model")), str(row.get("effective_from")))
            if not all(identity) or identity in identities:
                raise RegistryError("PRICING_ROW_INVALID_OR_DUPLICATE")
            identities.add(identity)
            parse_time(identity[2])
            if row.get("effective_to"):
                parse_time(str(row["effective_to"]))

    def select(self, provider: str, model: str, occurred_at: str) -> dict[str, Any] | None:
        at = parse_time(occurred_at)
        candidates = []
        for row in self.rows:
            if row.get("provider") != provider or row.get("model") != model:
                continue
            start = parse_time(str(row["effective_from"]))
            end = parse_time(str(row["effective_to"])) if row.get("effective_to") else None
            if start <= at and (end is None or at < end):
                candidates.append((start, row))
        if not candidates:
            return None
        selected = max(candidates, key=lambda item: item[0])[1]
        snapshot = dict(selected)
        snapshot["snapshot_digest"] = sha256_json(selected)
        return snapshot

    def with_rows(self, rows: Iterable[dict[str, Any]]) -> "PricingRegistry":
        clone = object.__new__(PricingRegistry)
        clone.rows = [*self.rows, *(dict(row) for row in rows)]
        clone.sources = list(self.sources)
        clone.snapshot = {"sources": clone.sources, "digest": sha256_json(clone.rows)}
        return clone
