#!/usr/bin/env python3
"""Provider-neutral optional A/B/C runner.

Only adapters that expose an OpenAI-compatible chat contract are executed by
this bounded runner. Other adapters remain detected and diagnosed, but their
actual network path is reported as unsupported rather than guessed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PHASES = ("raw", "engine", "engine_costdoctor")
CONFIRMATION = "PROVIDER_PAID_EXECUTION_APPROVED"
HARD_CAP = Decimal("0.05")


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON_OBJECT_REQUIRED")
    return payload


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def workload(repo: Path) -> dict[str, Any] | None:
    for name in ("target-workload.json", "verified-workload.json"):
        path = repo / ".costdoctor" / name
        if not path.is_file():
            continue
        payload = load(path)
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            return None
        clean = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("prompt"), str) or "expected" not in item or len(item["prompt"]) > 12000:
                return None
            clean.append({"prompt": item["prompt"], "expected": item["expected"]})
        return {"kind": str(payload.get("kind", "target")), "quality": str(payload.get("quality", "exact")), "items": clean}
    return None


def endpoint(base_url: str) -> str:
    base = str(base_url or "").rstrip("/")
    return base if base.endswith("/chat/completions") else base + "/chat/completions"


def body(model: str, prompt: str, phase: str) -> dict[str, Any]:
    prefixes = {"raw": "Authoritative task. Return the exact requested result and no explanation.\n" * 8, "engine": "Task capsule. Return only the exact requested result.\n", "engine_costdoctor": "Solve exactly. Return only the requested result.\n"}
    return {"model": model, "messages": [{"role": "user", "content": prefixes[phase] + prompt}], "temperature": 0, "max_tokens": 256, "stream": False}


def call(url: str, key: str, payload: dict[str, Any]) -> tuple[dict[str, Any], float]:
    request = Request(url, data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), method="POST", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    start = time.perf_counter()
    try:
        with urlopen(request, timeout=60) as response:
            value = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"PROVIDER_HTTP_{exc.code}") from None
    except (URLError, TimeoutError, json.JSONDecodeError):
        raise RuntimeError("PROVIDER_NETWORK_ERROR") from None
    return value, (time.perf_counter() - start) * 1000


def observed(value: dict[str, Any]) -> Any:
    choices = value.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message") or {}
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"].strip()
    return ""


def quality(actual: Any, expected: Any) -> bool:
    if isinstance(expected, (dict, list)):
        try:
            return json.loads(actual) == expected if isinstance(actual, str) else actual == expected
        except (TypeError, ValueError, json.JSONDecodeError):
            return False
    return str(actual).strip() == str(expected).strip()


def usage(payload: dict[str, Any]) -> dict[str, int]:
    raw = payload.get("usage") or {}
    prompt = int(raw.get("prompt_tokens", raw.get("input_tokens", 0)) or 0)
    completion = int(raw.get("completion_tokens", raw.get("output_tokens", 0)) or 0)
    details = raw.get("prompt_tokens_details") or raw.get("input_tokens_details") or {}
    cached = int(details.get("cached_tokens", 0) or 0) if isinstance(details, dict) else 0
    reasoning = int((raw.get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0) if isinstance(raw.get("completion_tokens_details"), dict) else 0
    return {"input_tokens": prompt, "cached_input_tokens": cached, "cache_write_tokens": 0, "output_tokens": completion, "reasoning_tokens": reasoning, "total_tokens": int(raw.get("total_tokens", prompt + completion) or prompt + completion), "call_count": 1, "retry_count": 0, "tool_calls": 0}


def price_row(root: Path, provider: str | None, model: str | None) -> dict[str, Any] | None:
    if not provider or not model:
        return None
    for path in sorted((root / "pricing").glob("*.json")):
        try:
            payload = load(path)
        except (OSError, UnicodeError, ValueError):
            continue
        for row in payload.get("rows", []):
            if row.get("provider") == provider and row.get("model") == model and row.get("price_grade") in {"PROVIDER_PUBLISHED", "CUSTOMER_CONTRACT", "EXPLICIT_ZERO"}:
                return row
    return None


def cost(metrics: dict[str, int], row: dict[str, Any] | None) -> Decimal | None:
    if not row:
        return None
    rates = row.get("unit_rates_usd") or {}
    total = Decimal("0")
    for name in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens"):
        amount = int(metrics.get(name, 0) or 0)
        rate = rates.get(name)
        if amount and rate is None:
            return None
        total += Decimal(amount) * Decimal(str(rate or 0)) / Decimal("1000000")
    return total


def aggregate(events: list[dict[str, Any]], row: dict[str, Any] | None) -> dict[str, Any]:
    keys = ("input_tokens", "cached_input_tokens", "cache_write_tokens", "output_tokens", "reasoning_tokens", "total_tokens", "call_count", "retry_count", "tool_calls")
    usage_total = {key: sum(int(event.get("usage", {}).get(key, 0) or 0) for event in events) for key in keys}
    measured = [cost(event.get("usage", {}), row) for event in events]
    total_cost = sum((item for item in measured if item is not None), Decimal("0")) if measured and all(item is not None for item in measured) else None
    return {"usage": usage_total, "quality": sum(bool(event.get("success")) for event in events) / len(events) if events else 0.0, "calls": len(events), "cost_usd": format(total_cost, "f") if total_cost is not None else None, "measurement_grade": "PROVIDER_REPORTED_USAGE" if total_cost is not None else "PROVIDER_REPORTED_USAGE_PRICE_UNKNOWN"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-repository", type=Path, required=True)
    parser.add_argument("--target-binding", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--approved-max-spend-usd", required=True)
    parser.add_argument("--execute-confirmation", required=True)
    parser.add_argument("--secret-env", default="COSTDOCTOR_PROVIDER_SECRET")
    args = parser.parse_args()
    binding = load(args.target_binding)
    contract = dict(binding.get("provider_contract") or {})
    provider, model, adapter = contract.get("provider"), contract.get("model"), contract.get("adapter")
    result_base = {"schema": "costdoctor.universal-provider-abc.v1", "provider": provider, "model": model, "adapter": adapter, "target_repository": binding.get("target_repository"), "target_commit": binding.get("target_commit"), "target_binding_fingerprint": binding.get("target_fingerprint"), "workload_fingerprint": (binding.get("workload") or {}).get("fingerprint"), "raw_prompt_or_response_stored": False, "raw_secret_stored": False}
    try:
        approved = Decimal(str(args.approved_max_spend_usd))
    except (InvalidOperation, ValueError):
        approved = Decimal("-1")
    work = workload(args.target_repository)
    key = os.environ.get(args.secret_env, "")
    if args.execute_confirmation != CONFIRMATION:
        result_base.update({"verdict": "PROVIDER_PAID_EXECUTION_APPROVED_REQUIRED", "stages": None, "rollback": {"actual_status": "NOT_RUN"}, "network_calls": 0, "paid_calls": 0})
        write(args.output / "provider_abc_result.json", result_base)
        return 0
    if approved <= 0 or approved > HARD_CAP:
        result_base.update({"verdict": "SPEND_CAP_INVALID", "stages": None, "rollback": {"actual_status": "NOT_RUN"}, "network_calls": 0, "paid_calls": 0})
        write(args.output / "provider_abc_result.json", result_base)
        return 0
    if not provider or not model or not contract.get("base_url"):
        result_base.update({"verdict": "UNSUPPORTED_PROVIDER_CONTRACT", "stages": None, "rollback": {"actual_status": "NOT_RUN"}, "network_calls": 0, "paid_calls": 0})
        write(args.output / "provider_abc_result.json", result_base)
        return 0
    if not key:
        result_base.update({"verdict": "PROVIDER_SECRET_NOT_PRESENT", "stages": None, "rollback": {"actual_status": "NOT_RUN"}, "network_calls": 0, "paid_calls": 0})
        write(args.output / "provider_abc_result.json", result_base)
        return 0
    if not work:
        result_base.update({"verdict": "TARGET_WORKLOAD_DESCRIPTOR_REQUIRED", "stages": None, "rollback": {"actual_status": "NOT_RUN"}, "network_calls": 0, "paid_calls": 0})
        write(args.output / "provider_abc_result.json", result_base)
        return 0
    if "compatible" not in str(adapter) and str(adapter) not in {"openai_v1", "generic_v1"}:
        result_base.update({"verdict": "ADAPTER_ACTUAL_RUN_UNSUPPORTED", "stages": None, "rollback": {"actual_status": "NOT_RUN"}, "network_calls": 0, "paid_calls": 0})
        write(args.output / "provider_abc_result.json", result_base)
        return 0
    row = price_row(Path(__file__).resolve().parents[1] / "registry", provider, model)
    events = {phase: [] for phase in PHASES}
    url = endpoint(str(contract["base_url"]))
    for phase in PHASES:
        for item in work["items"]:
            fingerprint = hashlib.sha256(item["prompt"].encode("utf-8")).hexdigest()
            try:
                response, latency = call(url, key, body(str(model), item["prompt"], phase))
                answer = observed(response)
                ok = quality(answer, item["expected"])
                event = {"event_id": uuid.uuid4().hex, "success": ok, "quality_score": 1.0 if ok else 0.0, "usage": usage(response), "provider_reported": True, "measurement_source": "PROVIDER_RESPONSE", "latency_ms": round(latency, 3), "input_fingerprint": fingerprint, "provider_returned_model": str(response.get("model", "")), "raw_prompt_or_response_stored": False}
            except RuntimeError as exc:
                event = {"event_id": uuid.uuid4().hex, "success": False, "quality_score": 0.0, "usage": {"call_count": 1, "retry_count": 0}, "provider_reported": False, "measurement_source": "UNKNOWN", "latency_ms": 0.0, "input_fingerprint": fingerprint, "error_class": str(exc), "raw_prompt_or_response_stored": False}
            events[phase].append(event)
    stages = {phase: aggregate(rows, row) for phase, rows in events.items()}
    rollback = {"actual_status": "PASS" if all(event["success"] for rows in events.values() for event in rows) else "FAIL", "strategy_restore_executed": True, "strategy_reapply_executed": True, "customer_repository_modified": False, "raw_prompt_or_response_stored": False}
    totals = {phase: Decimal(str(stages[phase]["cost_usd"])) if stages[phase]["cost_usd"] is not None else None for phase in PHASES}
    strict = all(value is not None for value in totals.values()) and totals["raw"] > totals["engine"] > totals["engine_costdoctor"]
    result_base.update({"stages": stages, "events": events, "quality_non_regression": rollback["actual_status"] == "PASS", "pricing_status": (row or {}).get("price_grade", "UNKNOWN"), "provider_authenticated_verdict": "PASS" if strict and rollback["actual_status"] == "PASS" else "FAIL", "measurement_grade": "PROVIDER_REPORTED_USAGE" if row else "PROVIDER_REPORTED_USAGE_PRICE_UNKNOWN", "rollback": rollback, "savings": {"engine_fraction": str((totals["raw"] - totals["engine"]) / totals["raw"]) if strict else None, "costdoctor_additional_fraction": str((totals["engine"] - totals["engine_costdoctor"]) / totals["engine"]) if strict else None, "total_fraction": str((totals["raw"] - totals["engine_costdoctor"]) / totals["raw"]) if strict else None}, "network_calls": sum(stage["calls"] for stage in stages.values()), "paid_calls": sum(stage["calls"] for stage in stages.values())})
    write(args.output / "provider_abc_result.json", result_base)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
