#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from copy import deepcopy
from decimal import Decimal, ROUND_UP
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from universal.costdoctor.benchmark import summarize_metrics
from universal.costdoctor.canonical import decimal_text, sha256_json, utc_now
from universal.costdoctor.evidence import UsageImporter
from universal.costdoctor.pricing import PricingEngine
from universal.costdoctor.registry import ModelRegistry, PricingRegistry, ProviderRegistry
from universal.costdoctor.request_adapters import build_llm_request
from universal.costdoctor.three_stage import build_three_stage_packet, render_three_stage_summary_ko
from universal.costdoctor.three_stage_validator import run_false_pass_probes, validate_three_stage


EXECUTION_CONFIRMATION = "PROVIDER_PAID_EXECUTION_APPROVED"
HARD_MAX_SPEND_USD = Decimal("0.05")
Transport = Callable[[dict[str, Any], str, str], tuple[dict[str, Any], float]]


class ProviderRunError(RuntimeError):
    pass


def load_spec(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "costdoctor.provider-benchmark-workloads.v1":
        raise ProviderRunError("PROVIDER_WORKLOAD_SCHEMA_INVALID")
    if payload.get("fresh_rounds") != 2 or len(payload.get("workloads", [])) < 2:
        raise ProviderRunError("PROVIDER_WORKLOAD_COVERAGE_INVALID")
    return payload


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def logical_binding(workload: dict[str, Any], commit: str) -> dict[str, Any]:
    body = {
        "id": workload["id"],
        "kind": workload["kind"],
        "goal": workload["goal"],
        "items": workload["items"],
    }
    return {
        "goal": workload["goal"],
        "input_fingerprint": sha256_json([row["value"] for row in workload["items"]]),
        "quality_criteria": "exact_numeric_match",
        "latency_limit_ms": 60000,
        "tool_permissions": [],
        "repetitions": 1,
        "environment_fingerprint": "openai-responses-live-v1",
        "workload_fingerprint": sha256_json(body),
        "commit": commit,
    }


def context_text(spec: dict[str, Any], phase: str) -> str:
    profile = spec["phase_context"][phase]
    return "\n".join([str(profile["text"])] * int(profile["repeat"]))


def build_request(spec: dict[str, Any], workload: dict[str, Any], item: dict[str, Any], phase: str, cache_key: str) -> dict[str, Any]:
    capsule = {
        "schema": "costdoctor.provider-task-capsule.v1",
        "goal": workload["goal"],
        "instructions": context_text(spec, phase),
        "public_fixture": item["value"],
        "output_contract": "one base-10 integer only",
    }
    envelope = build_llm_request(
        str(spec["provider"]),
        str(spec["model"]),
        capsule,
        max_output_tokens=int(spec["max_output_tokens"]),
        reasoning_effort=str(spec["reasoning_effort"]),
        cache_key=cache_key,
    )
    payload = envelope["request"]
    payload["store"] = False
    payload["text"] = {"verbosity": "low"}
    return payload


def _rate_row(pricing: PricingRegistry, provider: str, model: str) -> dict[str, Any]:
    rows = [row for row in pricing.rows if row.get("provider") == provider and row.get("model") == model]
    if len(rows) != 1 or rows[0].get("price_grade") != "PROVIDER_PUBLISHED":
        raise ProviderRunError("OFFICIAL_PRICE_ROW_REQUIRED")
    return rows[0]


def planned_requests(spec: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for round_index in range(int(spec["fresh_rounds"])):
        for workload in spec["workloads"]:
            for phase in ("raw", "engine", "engine_costdoctor", "rollback_raw", "reapply_engine_costdoctor"):
                request_phase = "raw" if phase == "rollback_raw" else "engine_costdoctor" if phase == "reapply_engine_costdoctor" else phase
                cache_key = sha256_json({"round": round_index, "workload": workload["id"], "phase": phase})
                for sequence, item in enumerate(workload["items"]):
                    payload = build_request(spec, workload, item, request_phase, cache_key)
                    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                    rows.append(
                        {
                            "round": round_index + 1,
                            "workload_id": workload["id"],
                            "phase": phase,
                            "sequence": sequence,
                            "request_bytes": len(encoded),
                            "request_fingerprint": sha256_json(payload),
                        }
                    )
    return rows


def conservative_forecast(spec: dict[str, Any], pricing: PricingRegistry) -> dict[str, Any]:
    rows = planned_requests(spec)
    price = _rate_row(pricing, str(spec["provider"]), str(spec["model"]))
    rates = price["unit_rates_usd"]
    input_rate = max(Decimal(str(rates[key])) for key in ("input_tokens", "cached_input_tokens", "cache_write_tokens"))
    output_rate = max(Decimal(str(rates[key])) for key in ("output_tokens", "reasoning_tokens"))
    input_upper = sum(int(row["request_bytes"]) for row in rows)
    output_upper = len(rows) * int(spec["max_output_tokens"])
    amount = (Decimal(input_upper) * input_rate + Decimal(output_upper) * output_rate) / Decimal("1000000")
    rounded = amount.quantize(Decimal("0.000001"), rounding=ROUND_UP)
    recommended = (rounded * Decimal("1.20")).quantize(Decimal("0.01"), rounding=ROUND_UP)
    return {
        "schema": "costdoctor.provider-spend-forecast.v1",
        "method": "UTF-8 request bytes as a conservative input-token ceiling; max_output_tokens as output ceiling; highest applicable published rate; no cache discount",
        "planned_calls": len(rows),
        "fresh_rounds": int(spec["fresh_rounds"]),
        "input_token_upper_bound": input_upper,
        "output_token_upper_bound": output_upper,
        "forecast_upper_bound_usd": decimal_text(rounded),
        "recommended_approval_usd": format(recommended, "f"),
        "hard_runner_cap_usd": format(HARD_MAX_SPEND_USD, "f"),
        "long_context_multiplier_applicable": False,
        "request_receipts": rows,
    }


def openai_transport(payload: dict[str, Any], api_key: str, endpoint: str) -> tuple[dict[str, Any], float]:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = Request(
        endpoint,
        data=data,
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ProviderRunError(f"PROVIDER_HTTP_{exc.code}") from None
    except URLError:
        raise ProviderRunError("PROVIDER_NETWORK_ERROR") from None
    except TimeoutError:
        raise ProviderRunError("PROVIDER_TIMEOUT") from None
    return body, (time.perf_counter() - started) * 1000


def parse_integer(body: dict[str, Any]) -> int | None:
    texts: list[str] = []
    if isinstance(body.get("output_text"), str):
        texts.append(body["output_text"])
    for item in body.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                texts.append(content["text"])
    for text in texts:
        match = re.fullmatch(r"\s*(-?\d+)\s*", text)
        if match:
            return int(match.group(1))
    return None


def execute_phase(
    spec: dict[str, Any],
    workload: dict[str, Any],
    phase_name: str,
    request_phase: str,
    round_index: int,
    commit: str,
    api_key: str,
    transport: Transport,
    importer: UsageImporter,
    pricing: PricingEngine,
) -> dict[str, Any]:
    run_id = f"{workload['id']}:{phase_name}:fresh-{round_index}:{uuid.uuid4().hex[:12]}"
    cache_key = sha256_json({"round": round_index, "workload": workload["id"], "phase": phase_name})
    records = []
    for sequence, item in enumerate(workload["items"]):
        payload = build_request(spec, workload, item, request_phase, cache_key)
        started_at = utc_now()
        input_fingerprint = sha256_json(item["value"])
        request_fingerprint = sha256_json(payload)
        try:
            body, latency_ms = transport(payload, api_key, str(spec["endpoint"]))
            actual = parse_integer(body)
            success = body.get("status") == "completed" and actual == int(item["expected"])
            record = {
                "event_id": f"{run_id}:{sequence}",
                "sequence": sequence,
                "started_at": started_at,
                "ended_at": utc_now(),
                "success": success,
                "error_class": None if success else "QUALITY_OR_COMPLETION_FAILURE",
                "usage": deepcopy(body.get("usage") or {}),
                "provider_reported": True,
                "provider_response_id": str(body.get("id", "")),
                "measurement_source": "PROVIDER_RESPONSE",
                "latency_ms": max(0.001, float(latency_ms)),
                "input_fingerprint": input_fingerprint,
                "context_fingerprint": sha256_json(context_text(spec, request_phase)),
                "quality_score": 1.0 if success else 0.0,
                "cache_hit": int((body.get("usage") or {}).get("input_tokens_details", {}).get("cached_tokens", 0)) > 0,
                "call_count": 1,
                "retry_count": 0,
                "tool_call_count": 0,
                "metadata": {
                    "provider_returned_model": str(body.get("model", "")),
                    "provider_status": str(body.get("status", "")),
                    "service_tier": str(body.get("service_tier", "")),
                    "answer_integer": actual,
                    "expected_integer": int(item["expected"]),
                    "request_fingerprint": request_fingerprint,
                    "request_bytes": len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")),
                    "raw_prompt_or_response_stored": False,
                    "rework": False,
                },
            }
        except ProviderRunError as exc:
            record = {
                "event_id": f"{run_id}:{sequence}",
                "sequence": sequence,
                "started_at": started_at,
                "ended_at": utc_now(),
                "success": False,
                "error_class": str(exc),
                "usage": {},
                "provider_reported": False,
                "provider_response_id": "",
                "measurement_source": "UNKNOWN",
                "latency_ms": 0.001,
                "input_fingerprint": input_fingerprint,
                "context_fingerprint": sha256_json(context_text(spec, request_phase)),
                "quality_score": 0.0,
                "cache_hit": False,
                "call_count": 1,
                "retry_count": 0,
                "tool_call_count": 0,
                "metadata": {
                    "request_fingerprint": request_fingerprint,
                    "raw_prompt_or_response_stored": False,
                    "rework": False,
                },
            }
        records.append(record)
    binding = logical_binding(workload, commit)
    context = {
        "workload_id": workload["id"],
        "run_id": run_id,
        "provider": spec["provider"],
        "model": spec["model"],
        "source_binding": {"commit": commit, "tree_state": "provider-actual-benchmark"},
        "environment_fingerprint": binding["environment_fingerprint"],
        "workload_fingerprint": binding["workload_fingerprint"],
    }
    evidence = importer.normalize_records(records, context)
    prices = [pricing.price_event(event) for event in evidence["events"]]
    returned_models = sorted({str(event.get("metadata", {}).get("provider_returned_model", "")) for event in evidence["events"]})
    if returned_models != [str(spec["model"])]:
        for event in evidence["events"]:
            event["success"] = False
            event["quality_score"] = 0.0
            event["error_class"] = "PROVIDER_RETURNED_MODEL_MISMATCH"
    return {"events": evidence["events"], "prices": prices, "binding": binding, "receipt_chain": evidence["receipts"], "returned_models": returned_models}


def phase_cost(phase: dict[str, Any]) -> Decimal | None:
    values = [row.get("cost_usd") for row in phase["prices"]]
    if any(value is None for value in values):
        return None
    return sum((Decimal(str(value)) for value in values), Decimal("0"))


def run_workload_round(
    spec: dict[str, Any],
    workload: dict[str, Any],
    round_index: int,
    commit: str,
    api_key: str,
    transport: Transport,
    importer: UsageImporter,
    pricing: PricingEngine,
) -> dict[str, Any]:
    started = time.perf_counter()
    phases = {}
    for phase in ("raw", "engine", "engine_costdoctor"):
        phases[phase] = execute_phase(spec, workload, phase, phase, round_index, commit, api_key, transport, importer, pricing)
        phases[phase]["overhead"] = {"cost_usd": "0.000000000", "wall_ms": 0, "included": True, "basis": "local optimizer compute has no metered API charge"}
    rollback_raw = execute_phase(spec, workload, "rollback_raw", "raw", round_index, commit, api_key, transport, importer, pricing)
    reapplied = execute_phase(spec, workload, "reapply_engine_costdoctor", "engine_costdoctor", round_index, commit, api_key, transport, importer, pricing)
    raw_ok = all(event["success"] and event["measurement"]["actual_provider_usage"] for event in rollback_raw["events"])
    reapply_ok = all(event["success"] and event["measurement"]["actual_provider_usage"] for event in reapplied["events"])
    raw_fingerprint = sha256_json({"phase": "raw", "binding": phases["raw"]["binding"], "quality": [event["quality_score"] for event in phases["raw"]["events"]]})
    rollback_fingerprint = sha256_json({"phase": "raw", "binding": rollback_raw["binding"], "quality": [event["quality_score"] for event in rollback_raw["events"]]})
    after_fingerprint = sha256_json({"phase": "engine_costdoctor", "binding": phases["engine_costdoctor"]["binding"], "quality": [event["quality_score"] for event in phases["engine_costdoctor"]["events"]]})
    reapply_fingerprint = sha256_json({"phase": "engine_costdoctor", "binding": reapplied["binding"], "quality": [event["quality_score"] for event in reapplied["events"]]})
    rollback = {
        "actual_status": "PASS" if raw_ok and reapply_ok and raw_fingerprint == rollback_fingerprint and after_fingerprint == reapply_fingerprint else "FAIL",
        "baseline_metrics_fingerprint": raw_fingerprint,
        "restored_before_metrics_fingerprint": rollback_fingerprint,
        "after_metrics_fingerprint": after_fingerprint,
        "reapplied_after_metrics_fingerprint": reapply_fingerprint,
        "strategy_restore_executed": True,
        "strategy_reapply_executed": True,
        "provider_calls": len(rollback_raw["events"]) + len(reapplied["events"]),
        "rollback_cost_usd": decimal_text(phase_cost(rollback_raw)) if phase_cost(rollback_raw) is not None else None,
        "reapply_cost_usd": decimal_text(phase_cost(reapplied)) if phase_cost(reapplied) is not None else None,
        "events": {"rollback_raw": rollback_raw["events"], "reapply_engine_costdoctor": reapplied["events"]},
        "prices": {"rollback_raw": rollback_raw["prices"], "reapply_engine_costdoctor": reapplied["prices"]},
    }
    phases["engine_costdoctor"]["overhead"]["wall_ms"] = round((time.perf_counter() - started) * 1000, 3)
    packet = build_three_stage_packet(
        workload["id"],
        phases,
        quality_threshold=float(workload["quality_threshold"]),
        rollback=rollback,
        context_receipts={
            "raw": {"fingerprint": sha256_json(context_text(spec, "raw")), "bytes": len(context_text(spec, "raw").encode("utf-8"))},
            "engine": {"fingerprint": sha256_json(context_text(spec, "engine")), "bytes": len(context_text(spec, "engine").encode("utf-8"))},
            "engine_costdoctor": {"fingerprint": sha256_json(context_text(spec, "engine_costdoctor")), "bytes": len(context_text(spec, "engine_costdoctor").encode("utf-8"))},
            "token_savings_claimed_from_bytes": False,
        },
        claim_scope="OpenAI Responses API provider-returned usage on public deterministic fixtures with official published pricing",
    )
    validation = validate_three_stage(packet)
    probes = run_false_pass_probes(packet)
    recurring_raw = Decimal(packet["phases"]["raw"]["net_cost_usd"]) if packet["phases"]["raw"]["net_cost_usd"] else None
    recurring_c = Decimal(packet["phases"]["engine_costdoctor"]["net_cost_usd"]) if packet["phases"]["engine_costdoctor"]["net_cost_usd"] else None
    rollback_cost = phase_cost(rollback_raw)
    reapply_cost = phase_cost(reapplied)
    experiment_net = None
    if None not in (recurring_raw, recurring_c, rollback_cost, reapply_cost):
        experiment_net = recurring_raw - recurring_c - rollback_cost - reapply_cost
    return {
        "packet": packet,
        "independent_validation": validation,
        "false_pass": probes,
        "rollback": rollback,
        "experiment_cost": {
            "rollback_and_reapply_cost_usd": decimal_text(rollback_cost + reapply_cost) if rollback_cost is not None and reapply_cost is not None else None,
            "retry_count": sum(event["usage"]["retry_count"] for phase in phases.values() for event in phase["events"]),
            "failed_call_count": sum(not event["success"] for phase in phases.values() for event in phase["events"]),
            "net_saving_after_rollback_reapply_usd": decimal_text(experiment_net) if experiment_net is not None else None,
        },
        "summary_ko": render_three_stage_summary_ko(packet, validation),
    }


def execute_all(spec: dict[str, Any], commit: str, api_key: str, transport: Transport = openai_transport) -> dict[str, Any]:
    models = ModelRegistry(ROOT / "universal" / "registry" / "models")
    providers = ProviderRegistry(ROOT / "universal" / "registry" / "providers")
    pricing_registry = PricingRegistry(ROOT / "universal" / "registry" / "pricing")
    if not models.resolve(str(spec["model"])):
        raise ProviderRunError("MODEL_REGISTRY_ROW_MISSING")
    _rate_row(pricing_registry, str(spec["provider"]), str(spec["model"]))
    importer = UsageImporter(models, providers)
    pricing = PricingEngine(pricing_registry)
    rounds = []
    for round_index in range(1, int(spec["fresh_rounds"]) + 1):
        workloads = []
        for workload in spec["workloads"]:
            workloads.append(run_workload_round(spec, workload, round_index, commit, api_key, transport, importer, pricing))
        rounds.append({"round": round_index, "workloads": workloads})
    pass_rows = [
        item["independent_validation"]["verdict"] == "PASS"
        and item["independent_validation"]["provider_actual_claim"] is True
        and item["false_pass"]["verdict"] == "PASS"
        and item["rollback"]["actual_status"] == "PASS"
        for round_row in rounds
        for item in round_row["workloads"]
    ]
    bindings = [
        item["packet"]["phases"]["raw"]["binding"]
        for round_row in rounds
        for item in round_row["workloads"]
    ]
    fresh_binding_match = all(binding == bindings[index % len(spec["workloads"])] for index, binding in enumerate(bindings))
    return {
        "schema": "costdoctor.provider-authenticated-abc.v1",
        "provider": spec["provider"],
        "model": spec["model"],
        "commit": commit,
        "rounds": rounds,
        "fresh_rounds": len(rounds),
        "fresh_binding_match": fresh_binding_match,
        "provider_authenticated_verdict": "PASS" if all(pass_rows) and fresh_binding_match else "FAIL",
        "privacy": {"secret_stored": False, "raw_prompt_stored": False, "raw_response_stored": False, "public_fixtures_only": True},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--execute-confirmation")
    parser.add_argument("--approved-max-spend-usd")
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit("OUTPUT_DIRECTORY_NOT_EMPTY")
    args.output.mkdir(parents=True, exist_ok=True)
    spec = load_spec(ROOT / "universal" / "workloads" / "provider-actual.v1.json")
    pricing = PricingRegistry(ROOT / "universal" / "registry" / "pricing")
    forecast = conservative_forecast(spec, pricing)
    key_present = bool(os.environ.get("OPENAI_API_KEY"))
    preflight = {
        "schema": "costdoctor.provider-actual-execution-preflight.v1",
        "provider": spec["provider"],
        "model": spec["model"],
        "commit": args.commit,
        "credential_present": key_present,
        "credential_value_stored_or_printed": False,
        "forecast": forecast,
        "execution_confirmation_valid": args.execute_confirmation == EXECUTION_CONFIRMATION,
        "approved_max_spend_usd": args.approved_max_spend_usd,
        "network_calls": 0,
        "paid_calls": 0,
    }
    write_json(args.output / "preflight.json", preflight)
    if args.preflight_only:
        preflight["verdict"] = "NEEDS_ACTION"
        preflight["reason"] = "EXACT_SPEND_APPROVAL_REQUIRED"
        write_json(args.output / "preflight.json", preflight)
        print(json.dumps({"verdict": preflight["verdict"], "forecast": forecast}, ensure_ascii=False, sort_keys=True))
        return 0
    if args.execute_confirmation != EXECUTION_CONFIRMATION:
        raise SystemExit("PAID_EXECUTION_CONFIRMATION_REQUIRED")
    if args.approved_max_spend_usd is None:
        raise SystemExit("EXACT_MAX_SPEND_APPROVAL_REQUIRED")
    approved = Decimal(args.approved_max_spend_usd)
    forecast_upper = Decimal(forecast["forecast_upper_bound_usd"])
    if approved <= 0 or approved > HARD_MAX_SPEND_USD:
        raise SystemExit("APPROVED_SPEND_CAP_INVALID_OR_ABOVE_HARD_LIMIT")
    if forecast_upper > approved:
        raise SystemExit("FORECAST_EXCEEDS_APPROVED_SPEND_CAP")
    if not key_present:
        raise SystemExit("OPENAI_API_KEY_REQUIRED")
    result = execute_all(spec, args.commit, os.environ["OPENAI_API_KEY"])
    actual_cost = Decimal("0")
    for round_row in result["rounds"]:
        for item in round_row["workloads"]:
            for phase in item["packet"]["phases"].values():
                actual_cost += Decimal(str(phase["net_cost_usd"]))
            rollback = item["rollback"]
            actual_cost += Decimal(str(rollback["rollback_cost_usd"])) + Decimal(str(rollback["reapply_cost_usd"]))
    if actual_cost > approved:
        result["provider_authenticated_verdict"] = "FAIL"
        result["spend_guard_failure"] = "ACTUAL_COST_EXCEEDED_APPROVED_CAP"
    result["spend"] = {
        "approved_max_spend_usd": decimal_text(approved),
        "actual_measured_cost_usd": decimal_text(actual_cost),
        "within_cap": actual_cost <= approved,
        "forecast_upper_bound_usd": forecast["forecast_upper_bound_usd"],
    }
    write_json(args.output / "provider_actual_result.json", result)
    print(json.dumps({"verdict": result["provider_authenticated_verdict"], "spend": result["spend"], "output": str(args.output)}, ensure_ascii=False, sort_keys=True))
    return 0 if result["provider_authenticated_verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
