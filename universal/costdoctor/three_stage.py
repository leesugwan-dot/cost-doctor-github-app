from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from statistics import mean
from typing import Any

from .benchmark import compare_bindings, summarize_metrics
from .canonical import decimal_text, sha256_json
from .measurement import weakest_measurement


PHASES = ("raw", "engine", "engine_costdoctor")


def _phase_cost(metrics: dict[str, Any], overhead: dict[str, Any]) -> Decimal | None:
    if metrics.get("total_cost_usd") is None or overhead.get("cost_usd") is None:
        return None
    return Decimal(str(metrics["total_cost_usd"])) + Decimal(str(overhead["cost_usd"]))


def _fraction(before: Decimal, after: Decimal) -> str | None:
    if before <= 0:
        return None
    return decimal_text((before - after) / before)


def _price_grade(prices: list[dict[str, Any]]) -> str:
    grades = []
    for price in prices:
        snapshot = price.get("pricing_snapshot") or {}
        grades.append(str(snapshot.get("price_grade", "UNVERIFIED")))
    if grades and all(grade in {"PROVIDER_PUBLISHED", "CUSTOMER_CONTRACT"} for grade in grades):
        return "VERIFIED_PRICE_SOURCE"
    if grades and all(grade == "FIXTURE" for grade in grades):
        return "FIXTURE_PRICE"
    return "UNVERIFIED_PRICE"


def build_three_stage_packet(workload_id: str, phases: dict[str, dict[str, Any]], *, quality_threshold: float, rollback: dict[str, Any], context_receipts: dict[str, Any], claim_scope: str) -> dict[str, Any]:
    if set(phases) != set(PHASES):
        raise ValueError("THREE_STAGE_PHASE_SET_INVALID")
    rows: dict[str, Any] = {}
    binding_failures: list[str] = []
    raw_binding = phases["raw"]["binding"]
    model_pairs: set[tuple[str, str]] = set()
    for name in PHASES:
        phase = phases[name]
        events = deepcopy(phase["events"])
        prices = deepcopy(phase["prices"])
        metrics = summarize_metrics(events, prices)
        overhead = deepcopy(phase.get("overhead") or {})
        cost = _phase_cost(metrics, overhead)
        quality_scores = [event.get("quality_score") for event in events]
        measurement = weakest_measurement(events)
        for event in events:
            model_pairs.add((str(event.get("provider")), str(event.get("model"))))
        if name != "raw":
            comparison = compare_bindings(raw_binding, phase["binding"])
            if comparison["verdict"] != "PASS":
                binding_failures.extend(f"{name}:{item}" for item in comparison["mismatches"])
        rows[name] = {
            "events": events,
            "prices": prices,
            "binding": deepcopy(phase["binding"]),
            "metrics": metrics,
            "overhead": overhead,
            "net_cost_usd": decimal_text(cost) if cost is not None else None,
            "measurement": measurement,
            "price_grade": _price_grade(prices),
            "quality": {"scores": quality_scores, "mean": round(mean(float(item) for item in quality_scores), 9) if quality_scores and all(item is not None for item in quality_scores) else None, "minimum": min(quality_scores) if quality_scores and all(item is not None for item in quality_scores) else None},
        }
    costs = {name: Decimal(rows[name]["net_cost_usd"]) if rows[name]["net_cost_usd"] is not None else None for name in PHASES}
    missing_quality = any(rows[name]["quality"]["minimum"] is None for name in PHASES)
    quality_failures = [name for name in PHASES if rows[name]["quality"]["minimum"] is not None and float(rows[name]["quality"]["minimum"]) < quality_threshold]
    raw_scores = rows["raw"]["quality"]["scores"]
    per_item_regression = []
    if not missing_quality:
        for name in ("engine", "engine_costdoctor"):
            scores = rows[name]["quality"]["scores"]
            if len(scores) != len(raw_scores) or any(float(after) < float(before) for before, after in zip(raw_scores, scores)):
                per_item_regression.append(name)
    measurement_unknown = any(rows[name]["measurement"]["rank"] == 0 for name in PHASES)
    if binding_failures or len(model_pairs) != 1:
        status, reason = "BLOCKED", "IDENTITY_OR_MODEL_BINDING_MISMATCH"
    elif missing_quality or measurement_unknown:
        status, reason = "NEEDS_EVIDENCE", "QUALITY_OR_MEASUREMENT_EVIDENCE_MISSING"
    elif quality_failures or per_item_regression:
        status, reason = "FAIL", "PER_WORKLOAD_QUALITY_GATE_FAILED"
    elif any(value is None for value in costs.values()):
        status, reason = "UNKNOWN", "PRICE_OR_OVERHEAD_UNKNOWN"
    elif not (costs["raw"] > costs["engine"] > costs["engine_costdoctor"]):
        status, reason = "FAIL", "NO_STRICT_THREE_STAGE_NET_SAVING"
    else:
        status, reason = "MEASURED_PENDING_INDEPENDENT_VALIDATION", "THREE_STAGE_MEASURED"
    all_provider_usage = all(rows[name]["measurement"].get("actual_provider_usage") is True for name in PHASES)
    all_verified_price = all(rows[name]["price_grade"] == "VERIFIED_PRICE_SOURCE" for name in PHASES)
    claim_grade = "PROVIDER_USAGE_WITH_VERIFIED_PRICE" if all_provider_usage and all_verified_price else "NON_PROVIDER_OR_UNVERIFIED_PRICE_MEASUREMENT"
    savings = {"engine_fraction": _fraction(costs["raw"], costs["engine"]) if costs["raw"] is not None and costs["engine"] is not None else None, "costdoctor_additional_fraction": _fraction(costs["engine"], costs["engine_costdoctor"]) if costs["engine"] is not None and costs["engine_costdoctor"] is not None else None, "total_fraction": _fraction(costs["raw"], costs["engine_costdoctor"]) if costs["raw"] is not None and costs["engine_costdoctor"] is not None else None}
    packet = {"schema": "costdoctor.three-stage-benchmark.v1", "workload_id": workload_id, "phases": rows, "quality_gate": {"threshold": quality_threshold, "missing": missing_quality, "failed_phases": quality_failures, "per_item_regression": per_item_regression}, "binding": {"verdict": "PASS" if not binding_failures and len(model_pairs) == 1 else "BLOCKED", "failures": binding_failures, "provider_model_pairs": sorted(model_pairs)}, "context_receipts": deepcopy(context_receipts), "rollback": deepcopy(rollback), "claim": {"status": status, "reason": reason, "grade": claim_grade, "savings": savings, "verified_savings_usd": None, "overhead_included": all("cost_usd" in rows[name]["overhead"] for name in PHASES)}, "claim_scope": claim_scope}
    packet["producer_digest"] = sha256_json(packet)
    return packet


def render_three_stage_summary_ko(packet: dict[str, Any], validation: dict[str, Any]) -> str:
    phases = packet["phases"]
    savings = packet["claim"]["savings"]
    pct = lambda value: "UNKNOWN" if value is None else f"{float(value) * 100:.2f}%"
    money = lambda value: "UNKNOWN" if value is None else f"${Decimal(str(value)):.9f}"
    measurement = phases["raw"]["measurement"]["grade"]
    return "\n".join([f"판정: {validation['verdict']}", f"원래 방식: {money(phases['raw']['net_cost_usd'])} → 기존 엔진: {money(phases['engine']['net_cost_usd'])} → 엔진+CostDoctor: {money(phases['engine_costdoctor']['net_cost_usd'])}", f"기존 엔진 절감: {pct(savings['engine_fraction'])} | CostDoctor 추가 절감: {pct(savings['costdoctor_additional_fraction'])} | 최종 총절감: {pct(savings['total_fraction'])}", f"품질: {phases['raw']['quality']['minimum']} → {phases['engine']['quality']['minimum']} → {phases['engine_costdoctor']['quality']['minimum']}", f"측정등급: {measurement} | 비용등급: {packet['claim']['grade']}"]) + "\n"
