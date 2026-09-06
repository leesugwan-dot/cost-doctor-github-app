from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from statistics import mean, median
from typing import Any

from .canonical import decimal_text, percentile, sha256_json, utc_now
from .quality import evaluate_quality


BINDING_KEYS = (
    "goal",
    "input_fingerprint",
    "quality_criteria",
    "latency_limit_ms",
    "tool_permissions",
    "repetitions",
    "environment_fingerprint",
    "workload_fingerprint",
    "commit",
)


def compare_bindings(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    mismatches = [key for key in BINDING_KEYS if before.get(key) != after.get(key)]
    return {"verdict": "PASS" if not mismatches else "BLOCKED", "mismatches": mismatches}


def summarize_metrics(events: list[dict[str, Any]], prices: list[dict[str, Any]]) -> dict[str, Any]:
    price_by_event = {price["event_id"]: price for price in prices}
    unknown = [event["event_id"] for event in events if price_by_event.get(event["event_id"], {}).get("status") == "UNKNOWN"]
    costs = []
    by_run: dict[str, Decimal] = {}
    for event in events:
        price = price_by_event.get(event["event_id"])
        if not price or price.get("cost_usd") is None:
            continue
        value = Decimal(str(price["cost_usd"]))
        costs.append(value)
        by_run[event["run_id"]] = by_run.get(event["run_id"], Decimal("0")) + value
    usage_keys = (
        "input_tokens",
        "output_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
        "tool_calls",
        "call_count",
        "retry_count",
    )
    totals = {key: sum(float(event["usage"].get(key, 0)) for event in events) for key in usage_keys}
    successes = sum(1 for event in events if event["success"])
    run_costs = [float(value) for value in by_run.values()]
    total_cost = sum(costs, Decimal("0")) if not unknown and len(prices) == len(events) else None
    quality_scores = [float(event["quality_score"]) for event in events if event.get("quality_score") is not None]
    quality_mean = mean(quality_scores) if quality_scores else None
    return {
        "event_count": len(events),
        "repetitions": len({event["run_id"] for event in events}),
        "pricing_status": "KNOWN" if total_cost is not None else "UNKNOWN",
        "unknown_price_event_count": len(unknown),
        "total_cost_usd": decimal_text(total_cost) if total_cost is not None else None,
        "cost_per_success_usd": decimal_text(total_cost / successes) if total_cost is not None and successes else None,
        "quality_adjusted_cost_usd": decimal_text(total_cost / Decimal(str(quality_mean))) if total_cost is not None and quality_mean else None,
        "total_tokens": int(sum(totals[key] for key in usage_keys[:5])),
        "usage": {key: int(value) for key, value in totals.items()},
        "successes": successes,
        "failures": len(events) - successes,
        "completion_rate": round(successes / len(events), 9) if events else 0,
        "latency_p50_ms": round(percentile((event["latency_ms"] for event in events), 0.50), 6),
        "latency_p95_ms": round(percentile((event["latency_ms"] for event in events), 0.95), 6),
        "cache_hit_rate": round(sum(1 for event in events if event.get("cache_hit")) / len(events), 9) if events else 0,
        "rework_rate": round(sum(1 for event in events if event.get("metadata", {}).get("rework")) / len(events), 9) if events else 0,
        "quality_mean": round(quality_mean, 9) if quality_mean is not None else None,
        "run_cost_usd": [decimal_text(Decimal(str(value))) for value in run_costs],
        "run_cost_mean_usd": decimal_text(Decimal(str(mean(run_costs)))) if run_costs else None,
        "run_cost_median_usd": decimal_text(Decimal(str(median(run_costs)))) if run_costs else None,
        "run_cost_range_usd": decimal_text(Decimal(str(max(run_costs) - min(run_costs)))) if run_costs else None,
    }


def build_benchmark_packet(
    workload_id: str,
    before_events: list[dict[str, Any]],
    after_events: list[dict[str, Any]],
    before_prices: list[dict[str, Any]],
    after_prices: list[dict[str, Any]],
    before_binding: dict[str, Any],
    after_binding: dict[str, Any],
    threshold: float,
    rollback: dict[str, Any],
    detectors: list[dict[str, Any]],
    routing: dict[str, Any],
    claim_scope: str,
) -> dict[str, Any]:
    binding = compare_bindings(before_binding, after_binding)
    before_metrics = summarize_metrics(before_events, before_prices)
    after_metrics = summarize_metrics(after_events, after_prices)
    quality = evaluate_quality(
        [event["quality_score"] for event in before_events if event.get("quality_score") is not None],
        [event["quality_score"] for event in after_events if event.get("quality_score") is not None],
        threshold,
    )
    claim: dict[str, Any]
    if binding["verdict"] != "PASS":
        claim = {"status": "BLOCKED", "reason": "BINDING_MISMATCH", "verified_savings_usd": None}
    elif before_metrics["repetitions"] < 2 or after_metrics["repetitions"] < 2:
        claim = {"status": "INCONCLUSIVE", "reason": "MULTIPLE_REPETITIONS_REQUIRED", "verified_savings_usd": None}
    elif before_metrics["pricing_status"] != "KNOWN" or after_metrics["pricing_status"] != "KNOWN":
        claim = {"status": "UNKNOWN", "reason": "PRICE_UNKNOWN", "verified_savings_usd": None}
    elif quality["verdict"] != "PASS":
        claim = {"status": "FAIL", "reason": quality["reason"], "verified_savings_usd": None}
    else:
        before_cost = Decimal(before_metrics["total_cost_usd"])
        after_cost = Decimal(after_metrics["total_cost_usd"])
        saving = before_cost - after_cost
        if saving <= 0:
            claim = {"status": "NO_SAVINGS", "reason": "COST_DID_NOT_DECREASE", "verified_savings_usd": None}
        else:
            claim = {
                "status": "MEASURED_PENDING_INDEPENDENT_VALIDATION",
                "reason": "COST_DOWN_QUALITY_PASS",
                "measured_savings_usd": decimal_text(saving),
                "verified_savings_usd": None,
            }
    packet = {
        "schema": "costdoctor.benchmark-evidence.v1",
        "producer": "costdoctor-universal-1.0.0",
        "generated_at": utc_now(),
        "workload_id": workload_id,
        "claim_scope": claim_scope,
        "bindings": {"before": deepcopy(before_binding), "after": deepcopy(after_binding), "comparison": binding},
        "before": {"events": deepcopy(before_events), "prices": deepcopy(before_prices), "metrics": before_metrics},
        "after": {"events": deepcopy(after_events), "prices": deepcopy(after_prices), "metrics": after_metrics},
        "quality": quality,
        "detectors": deepcopy(detectors),
        "routing_advisor": deepcopy(routing),
        "rollback": deepcopy(rollback),
        "claim": claim,
        "claim_level": 4 if claim["status"] == "MEASURED_PENDING_INDEPENDENT_VALIDATION" else 3,
    }
    packet["producer_digest"] = sha256_json(packet)
    return packet


def refresh_packet_digest(packet: dict[str, Any]) -> dict[str, Any]:
    clone = deepcopy(packet)
    clone.pop("producer_digest", None)
    clone.pop("independent_validation", None)
    packet["producer_digest"] = sha256_json(clone)
    return packet
