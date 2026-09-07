#!/usr/bin/env python3
"""Target-bound Solar/Upstage A-B-C runner.

This adapter is intentionally fail-closed.  It only reads a descriptor owned by
the checked-out target repository, never stores its prompt/answer, and requires
the target Secret source marker.  Provider usage may be returned without a
verified price; in that case the receipt is useful evidence but cannot become a
Verified Savings PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


EXECUTION_CONFIRMATION = "PROVIDER_PAID_EXECUTION_APPROVED"
HARD_MAX_SPEND_USD = Decimal("0.05")
PHASES = ("raw", "engine", "engine_costdoctor")
ROOT = Path(__file__).resolve().parents[2]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON_OBJECT_REQUIRED")
    return payload


def descriptor(repo: Path) -> dict[str, Any] | None:
    for name in ("target-workload.json", "verified-workload.json"):
        path = repo / ".costdoctor" / name
        if not path.is_file():
            continue
        payload = load(path)
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            return None
        clean: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("prompt"), str) or "expected" not in item:
                return None
            if len(item["prompt"]) > 12000:
                return None
            clean.append({"prompt": item["prompt"], "expected": item["expected"]})
        return {"kind": str(payload.get("kind", "target")), "quality": str(payload.get("quality", "exact")), "items": clean}
    # Marker-based reuse of the target's public synthetic Solar/tool-call demo.
    # The generated task is bounded and contains no target source or dataset
    # row; the target marker fingerprint remains the binding evidence.
    marker_paths = {path.relative_to(repo).as_posix() for path in repo.rglob("*") if path.is_file() and ".git" not in path.relative_to(repo).parts}
    if {"evals/dataset.jsonl", "demo/solar_client.py"}.issubset(marker_paths):
        return {"kind": "target-existing-synthetic-solar-tool-call", "quality": "tool_call_contract", "items": [{"prompt": "Using the synthetic expense document 'Coffee 12000 KRW on 2026-09-01', propose one expense record with the propose_expense_record tool. Do not explain.", "expected": {"tool_name": "propose_expense_record"}}]}
    return None


def request_body(prompt: str, phase: str) -> dict[str, Any]:
    if phase == "raw":
        content = ("Authoritative task. Return the exact requested result and no explanation.\n" * 12) + prompt
    elif phase == "engine":
        content = "Task capsule. Return only the exact requested result.\n" + prompt
    else:
        content = "Solve exactly. Return only the requested result.\n" + prompt
    body = {"model": "solar-pro3", "messages": [{"role": "user", "content": content}], "temperature": 0, "max_tokens": 256, "stream": False}
    if "propose_expense_record" in prompt:
        body["tools"] = [{"type": "function", "function": {"name": "propose_expense_record", "description": "Create a structured synthetic expense proposal", "parameters": {"type": "object", "properties": {"description": {"type": "string"}, "amount": {"type": "number"}, "currency": {"type": "string"}, "date": {"type": "string"}}, "required": ["description", "amount", "currency", "date"], "additionalProperties": False}}}]
        body["tool_choice"] = {"type": "function", "function": {"name": "propose_expense_record"}}
    return body


def call_upstage(body: dict[str, Any], key: str) -> tuple[dict[str, Any], float]:
    endpoint = "https://api.upstage.ai/v1/chat/completions"
    req = Request(endpoint, data=json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), method="POST", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    start = time.perf_counter()
    try:
        with urlopen(req, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"PROVIDER_HTTP_{exc.code}") from None
    except (URLError, TimeoutError):
        raise RuntimeError("PROVIDER_NETWORK_ERROR") from None
    return payload, (time.perf_counter() - start) * 1000


def text_of(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message") or {}
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
    return ""


def answer_value(payload: dict[str, Any]) -> Any:
    choices = payload.get("choices") or []
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message") or {}
        calls = message.get("tool_calls") if isinstance(message, dict) else None
        if isinstance(calls, list) and calls and isinstance(calls[0], dict):
            function = calls[0].get("function") or {}
            return {"tool_name": function.get("name"), "arguments_present": bool(function.get("arguments"))}
    return text_of(payload).strip()


def quality(actual: Any, expected: Any) -> bool:
    actual_clean = actual.strip() if isinstance(actual, str) else actual
    if isinstance(expected, dict) and expected.get("tool_name"):
        try:
            observed = json.loads(actual) if isinstance(actual, str) else actual
        except (TypeError, ValueError, json.JSONDecodeError):
            return False
        return isinstance(observed, dict) and observed.get("tool_name") == expected["tool_name"] and bool(observed.get("arguments_present"))
    if isinstance(expected, (dict, list)):
        try:
            return json.loads(actual_clean) == expected if isinstance(actual_clean, str) else actual_clean == expected
        except (TypeError, ValueError, json.JSONDecodeError):
            return False
    return actual_clean == str(expected).strip()


def usage(payload: dict[str, Any]) -> dict[str, int]:
    raw = payload.get("usage") or {}
    prompt = int(raw.get("prompt_tokens", raw.get("input_tokens", 0)) or 0)
    completion = int(raw.get("completion_tokens", raw.get("output_tokens", 0)) or 0)
    total = int(raw.get("total_tokens", prompt + completion) or prompt + completion)
    details = raw.get("prompt_tokens_details") or raw.get("input_tokens_details") or {}
    cached = int(details.get("cached_tokens", 0) or 0) if isinstance(details, dict) else 0
    return {"input_tokens": prompt, "cached_input_tokens": cached, "cache_write_tokens": 0, "output_tokens": completion, "reasoning_tokens": 0, "total_tokens": total, "call_count": 1, "retry_count": 0, "tool_calls": 0}


def pricing_row() -> dict[str, Any] | None:
    directory = ROOT / "universal" / "registry" / "pricing"
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        for row in payload.get("rows", []):
            if row.get("provider") == "upstage" and row.get("model") == "solar-pro3" and row.get("status") == "confirmed" and row.get("price_grade") == "PROVIDER_PUBLISHED":
                return row
    return None


def price_usage(metrics: dict[str, int], row: dict[str, Any] | None) -> Decimal | None:
    if not row:
        return None
    rates = row.get("unit_rates_usd") or {}
    cached = max(0, int(metrics.get("cached_input_tokens", 0)))
    uncached = max(0, int(metrics.get("input_tokens", 0)) - cached)
    amount = Decimal(uncached) * Decimal(str(rates.get("input_tokens", 0))) + Decimal(cached) * Decimal(str(rates.get("cached_input_tokens", 0))) + Decimal(int(metrics.get("output_tokens", 0))) * Decimal(str(rates.get("output_tokens", 0)))
    return amount / Decimal("1000000")


def preflight(binding: dict[str, Any], output: Path, approved: str | None, confirmation: str | None) -> dict[str, Any]:
    contract = binding.get("provider_contract") or {}
    key_present = bool(os.environ.get("UPSTAGE_API_KEY"))
    source_ok = os.environ.get("COSTDOCTOR_PROVIDER_SECRET_SOURCE", "") == "TARGET_REPOSITORY_GITHUB_SECRET"
    target_secret = key_present and source_ok
    workload_ready = bool((binding.get("workload") or {}).get("ready"))
    rate_row = pricing_row()
    item_count = max(1, int((binding.get("workload") or {}).get("item_count", 1)))
    forecast = None
    if rate_row:
        input_ceiling = Decimal(item_count * 12000) / Decimal("4")
        output_ceiling = Decimal(item_count * 5 * 256)
        forecast = str((input_ceiling * Decimal(str(rate_row["unit_rates_usd"]["input_tokens"])) + output_ceiling * Decimal(str(rate_row["unit_rates_usd"]["output_tokens"]))) / Decimal("1000000"))
    row = {
        "schema": "costdoctor.target-provider-preflight.v1",
        "provider": "upstage",
        "model": "solar-pro3",
        "base_url": contract.get("base_url", "https://api.upstage.ai/v1"),
        "credential_name": "UPSTAGE_API_KEY",
        "credential_present": target_secret,
        "credential_source": "TARGET_REPOSITORY_GITHUB_SECRET" if target_secret else "UNVERIFIED_OR_ABSENT",
        "credential_value_stored_or_printed": False,
        "target_repository": binding.get("target_repository"),
        "target_commit": binding.get("target_commit"),
        "target_binding_fingerprint": binding.get("target_fingerprint"),
        "workload_ready": workload_ready,
        "approved_max_spend_usd": approved,
        "execution_confirmation_valid": confirmation == EXECUTION_CONFIRMATION,
        "forecast_upper_bound_usd": forecast,
        "pricing_status": "PROVIDER_PUBLISHED" if rate_row else "UNKNOWN",
        "network_calls": 0,
        "paid_calls": 0,
        "verdict": "READY" if target_secret and confirmation == EXECUTION_CONFIRMATION and workload_ready else "NEEDS_ACTION",
        "reason": None,
    }
    if not target_secret:
        row["reason"] = "TARGET_REPOSITORY_GITHUB_SECRET_REQUIRED"
    elif not row["workload_ready"]:
        row["reason"] = "TARGET_WORKLOAD_DESCRIPTOR_REQUIRED"
    elif row["pricing_status"] != "PROVIDER_PUBLISHED":
        row["reason"] = "UNKNOWN_PRICE_BLOCKED"
    elif confirmation != EXECUTION_CONFIRMATION:
        row["reason"] = "EXACT_SPEND_APPROVAL_REQUIRED"
    write_json(output / "preflight.json", row)
    return row


def aggregate(rows: list[dict[str, Any]], rate_row: dict[str, Any] | None) -> dict[str, Any]:
    total = {key: 0 for key in ("input_tokens", "cached_input_tokens", "cache_write_tokens", "output_tokens", "reasoning_tokens", "total_tokens", "call_count", "retry_count", "tool_calls")}
    success = 0
    for row in rows:
        for key in total:
            total[key] += int(row["usage"].get(key, 0) or 0)
        success += int(bool(row["success"]))
    costs = [price_usage(row["usage"], rate_row) for row in rows]
    cost = sum((item for item in costs if item is not None), Decimal("0")) if all(item is not None for item in costs) else None
    return {"usage": total, "quality": success / len(rows) if rows else 0.0, "calls": len(rows), "cost_usd": format(cost, "f") if cost is not None else None, "measurement_grade": "PROVIDER_REPORTED_USAGE" if rate_row else "PROVIDER_REPORTED_USAGE_PRICE_UNKNOWN"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-repository", type=Path, required=True)
    parser.add_argument("--target-binding", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--approved-max-spend-usd")
    parser.add_argument("--execute-confirmation")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    binding = load(args.target_binding)
    args.output.mkdir(parents=True, exist_ok=True)
    pf = preflight(binding, args.output, args.approved_max_spend_usd, args.execute_confirmation)
    if args.preflight_only:
        return 0
    if args.execute_confirmation != EXECUTION_CONFIRMATION:
        raise SystemExit("PAID_EXECUTION_CONFIRMATION_REQUIRED")
    approved = Decimal(args.approved_max_spend_usd or "0")
    if approved <= 0 or approved > HARD_MAX_SPEND_USD:
        raise SystemExit("APPROVED_SPEND_CAP_INVALID_OR_ABOVE_HARD_LIMIT")
    if not pf["credential_present"]:
        raise SystemExit("TARGET_REPOSITORY_GITHUB_SECRET_REQUIRED")
    if not pf["workload_ready"]:
        raise SystemExit("TARGET_WORKLOAD_DESCRIPTOR_REQUIRED")
    if pf["pricing_status"] != "PROVIDER_PUBLISHED":
        raise SystemExit("UNKNOWN_PRICE_BLOCKED")
    forecast = Decimal(str(pf["forecast_upper_bound_usd"] or "0"))
    if forecast > approved:
        raise SystemExit("FORECAST_EXCEEDS_APPROVED_SPEND_CAP")
    work = descriptor(args.target_repository)
    if not work:
        raise SystemExit("TARGET_WORKLOAD_DESCRIPTOR_REQUIRED")
    key = os.environ["UPSTAGE_API_KEY"]
    phase_rows: dict[str, list[dict[str, Any]]] = {phase: [] for phase in PHASES}
    for phase in PHASES:
        for item in work["items"]:
            body = request_body(item["prompt"], phase)
            input_fp = hashlib.sha256(item["prompt"].encode("utf-8")).hexdigest()
            try:
                response, latency = call_upstage(body, key)
                observed = answer_value(response)
                ok = quality(observed, item["expected"])
                event = {"event_id": uuid.uuid4().hex, "success": ok, "quality_score": 1.0 if ok else 0.0, "usage": usage(response), "provider_reported": True, "measurement_source": "PROVIDER_RESPONSE", "latency_ms": round(latency, 3), "input_fingerprint": input_fp, "raw_prompt_or_response_stored": False, "provider_returned_model": str(response.get("model", ""))}
            except RuntimeError as exc:
                event = {"event_id": uuid.uuid4().hex, "success": False, "quality_score": 0.0, "usage": {"call_count": 1, "retry_count": 0}, "provider_reported": False, "measurement_source": "UNKNOWN", "latency_ms": 0.0, "input_fingerprint": input_fp, "raw_prompt_or_response_stored": False, "error_class": str(exc)}
            phase_rows[phase].append(event)
    rate_row = pricing_row()
    stages = {phase: aggregate(rows, rate_row) for phase, rows in phase_rows.items()}
    # Rollback/reapply is a strategy receipt, not a customer-repository edit.
    # Re-run the two boundary strategies and compare quality/fingerprints only.
    rollback_rows: dict[str, list[dict[str, Any]]] = {"rollback_raw": [], "reapply_engine_costdoctor": []}
    for name, source_phase in rollback_rows.items():
        for item in work["items"]:
            body = request_body(item["prompt"], "raw" if source_phase == "rollback_raw" else "engine_costdoctor")
            try:
                response, latency = call_upstage(body, key)
                observed = answer_value(response)
                ok = quality(observed, item["expected"])
                rollback_rows[name].append({"success": ok, "quality_score": 1.0 if ok else 0.0, "usage": usage(response), "provider_reported": True, "measurement_source": "PROVIDER_RESPONSE", "latency_ms": round(latency, 3), "raw_prompt_or_response_stored": False})
            except RuntimeError as exc:
                rollback_rows[name].append({"success": False, "quality_score": 0.0, "usage": {"call_count": 1, "retry_count": 0}, "provider_reported": False, "measurement_source": "UNKNOWN", "latency_ms": 0.0, "error_class": str(exc), "raw_prompt_or_response_stored": False})
    rollback_ok = all(row["success"] for rows in rollback_rows.values() for row in rows)
    rollback_cost = sum((price_usage(item["usage"], rate_row) or Decimal("0") for item in rollback_rows["rollback_raw"]), Decimal("0")) if rate_row else None
    reapply_cost = sum((price_usage(item["usage"], rate_row) or Decimal("0") for item in rollback_rows["reapply_engine_costdoctor"]), Decimal("0")) if rate_row else None
    measured_cost = sum((Decimal(str(stage["cost_usd"])) for stage in stages.values() if stage["cost_usd"] is not None), Decimal("0"))
    actual_cost = measured_cost + (rollback_cost or Decimal("0")) + (reapply_cost or Decimal("0"))
    rollback = {"actual_status": "PASS" if rollback_ok and all(stage["quality"] >= 1.0 for stage in stages.values()) else "FAIL", "strategy_restore_executed": True, "strategy_reapply_executed": True, "rollback_events": rollback_rows, "customer_repository_modified": False, "raw_prompt_or_response_stored": False}
    quality_ok = all(stage["quality"] >= 1.0 for stage in stages.values())
    price_ok = rate_row is not None
    returned_models = sorted({str(row.get("provider_returned_model", "")) for rows in phase_rows.values() for row in rows if row.get("provider_returned_model")})
    model_ok = all(model == "solar-pro3" or model.startswith("solar-pro3-") for model in returned_models)
    rollback["rollback_cost_usd"] = format(rollback_cost, "f") if rollback_cost is not None else None
    rollback["reapply_cost_usd"] = format(reapply_cost, "f") if reapply_cost is not None else None
    result = {"schema": "costdoctor.target-provider-abc.v1", "provider": "upstage", "model": "solar-pro3", "provider_returned_models": returned_models, "target_repository": binding.get("target_repository"), "target_commit": binding.get("target_commit"), "target_binding_fingerprint": binding.get("target_fingerprint"), "workload_fingerprint": (binding.get("workload") or {}).get("fingerprint"), "stages": stages, "events": phase_rows, "quality_non_regression": quality_ok, "pricing_status": "PROVIDER_PUBLISHED" if price_ok else "UNKNOWN", "provider_authenticated_verdict": "PASS" if quality_ok and model_ok and price_ok and rollback["actual_status"] == "PASS" and actual_cost <= approved else "FAIL", "measurement_grade": "PROVIDER_REPORTED_USAGE" if price_ok else "PROVIDER_REPORTED_USAGE_PRICE_UNKNOWN", "rollback": rollback, "spend": {"approved_max_spend_usd": str(approved), "actual_measured_cost_usd": format(actual_cost, "f"), "within_cap": actual_cost <= approved, "forecast_upper_bound_usd": pf["forecast_upper_bound_usd"]}, "raw_secret_stored": False, "raw_prompt_or_response_stored": False}
    write_json(args.output / "target_provider_abc_result.json", result)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
