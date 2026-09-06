from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .canonical import decimal_text, sha256_json
from .measurement import assert_no_grade_promotion


TOKEN_UNITS = ("input_tokens", "output_tokens", "cached_input_tokens", "cache_write_tokens", "reasoning_tokens")
PHASES = ("raw", "engine", "engine_costdoctor")


def _price(event: dict[str, Any], price: dict[str, Any]) -> Decimal | None:
    snapshot = price.get("pricing_snapshot") or {}
    rates = snapshot.get("unit_rates_usd") or {}
    if price.get("status") == "UNKNOWN" or not rates:
        return None
    total = Decimal("0")
    for unit in TOKEN_UNITS:
        quantity = Decimal(str(event.get("usage", {}).get(unit, 0)))
        if quantity and rates.get(unit) is None:
            return None
        total += quantity * Decimal(str(rates.get(unit, 0))) / Decimal("1000000")
    tool_calls = Decimal(str(event.get("usage", {}).get("tool_calls", 0)))
    if tool_calls and rates.get("tool_calls") is None:
        return None
    total += tool_calls * Decimal(str(rates.get("tool_calls", 0)))
    if event.get("batch"):
        total *= Decimal("1") - Decimal(str(snapshot.get("batch_discount_fraction", 0)))
    total = max(total, Decimal(str(snapshot.get("request_minimum_usd", 0))))
    quantum = Decimal(1).scaleb(-int(snapshot.get("rounding_decimals", 9)))
    return total.quantize(quantum, rounding=ROUND_HALF_UP)


def _fraction(before: Decimal, after: Decimal) -> str | None:
    return decimal_text((before - after) / before) if before > 0 else None


def validate_three_stage(packet: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    body = deepcopy(packet)
    claimed_digest = body.pop("producer_digest", None)
    if claimed_digest != sha256_json(body):
        failures.append("PRODUCER_DIGEST_MISMATCH")
    if packet.get("schema") != "costdoctor.three-stage-benchmark.v1":
        failures.append("SCHEMA_INVALID")
    phases = packet.get("phases") or {}
    if set(phases) != set(PHASES):
        failures.append("PHASE_SET_INVALID")
        return _result(packet, failures, {})
    raw_binding = phases["raw"].get("binding")
    costs: dict[str, Decimal] = {}
    model_pairs = set()
    actual_usage_flags: list[bool] = []
    price_grades: list[str] = []
    raw_quality: dict[int, float] = {}
    for name in PHASES:
        phase = phases[name]
        if phase.get("binding") != raw_binding:
            failures.append(f"{name.upper()}_BINDING_MISMATCH")
        price_by_id = {row.get("event_id"): row for row in phase.get("prices", [])}
        phase_cost = Decimal("0")
        quality: dict[int, float] = {}
        for event in phase.get("events", []):
            model_pairs.add((event.get("provider"), event.get("model")))
            event_body = deepcopy(event)
            event_digest = event_body.pop("event_digest", None)
            if event_digest != sha256_json(event_body):
                failures.append(f"{name.upper()}_EVENT_DIGEST_MISMATCH")
            if not assert_no_grade_promotion(event):
                failures.append(f"{name.upper()}_MEASUREMENT_GRADE_PROMOTION")
            actual_usage_flags.append(event.get("measurement", {}).get("actual_provider_usage") is True)
            price_row = price_by_id.get(event.get("event_id"), {})
            snapshot = price_row.get("pricing_snapshot") or {}
            snapshot_body = deepcopy(snapshot)
            snapshot_digest = snapshot_body.pop("snapshot_digest", None)
            if not snapshot_digest or snapshot_digest != sha256_json(snapshot_body) or price_row.get("pricing_snapshot_digest") != snapshot_digest:
                failures.append(f"{name.upper()}_PRICE_SNAPSHOT_DIGEST_MISMATCH")
            price_grades.append(str(snapshot.get("price_grade", "UNVERIFIED")))
            calculated = _price(event, price_row)
            if calculated is None:
                failures.append(f"{name.upper()}_PRICE_UNKNOWN")
            else:
                claimed = price_by_id[event["event_id"]].get("cost_usd")
                if claimed is None or Decimal(str(claimed)) != calculated:
                    failures.append(f"{name.upper()}_PRICE_RECOMPUTE_MISMATCH")
                phase_cost += calculated
            if event.get("quality_score") is None:
                failures.append(f"{name.upper()}_QUALITY_MISSING")
            else:
                quality[int(event["sequence"])] = float(event["quality_score"])
        overhead = phase.get("overhead")
        if not isinstance(overhead, dict) or overhead.get("cost_usd") is None:
            failures.append(f"{name.upper()}_OVERHEAD_MISSING")
        else:
            phase_cost += Decimal(str(overhead["cost_usd"]))
        costs[name] = phase_cost
        if phase.get("net_cost_usd") is None or Decimal(str(phase["net_cost_usd"])) != phase_cost:
            failures.append(f"{name.upper()}_NET_COST_MISMATCH")
        if name == "raw":
            raw_quality = quality
        elif set(quality) != set(raw_quality) or any(quality[key] < raw_quality[key] for key in raw_quality):
            failures.append(f"{name.upper()}_PER_ITEM_QUALITY_REGRESSION")
        threshold = float(packet.get("quality_gate", {}).get("threshold", 1))
        if quality and min(quality.values()) < threshold:
            failures.append(f"{name.upper()}_QUALITY_THRESHOLD_FAILED")
    if len(model_pairs) != 1:
        failures.append("PROVIDER_MODEL_CHANGED")
    provider_actual = bool(actual_usage_flags) and all(actual_usage_flags) and bool(price_grades) and all(grade in {"PROVIDER_PUBLISHED", "CUSTOMER_CONTRACT"} for grade in price_grades)
    expected_claim_grade = "PROVIDER_USAGE_WITH_VERIFIED_PRICE" if provider_actual else "NON_PROVIDER_OR_UNVERIFIED_PRICE_MEASUREMENT"
    if packet.get("claim", {}).get("grade") != expected_claim_grade:
        failures.append("CLAIM_GRADE_PROMOTION")
    expected = {"engine_fraction": _fraction(costs["raw"], costs["engine"]), "costdoctor_additional_fraction": _fraction(costs["engine"], costs["engine_costdoctor"]), "total_fraction": _fraction(costs["raw"], costs["engine_costdoctor"])}
    if packet.get("claim", {}).get("savings") != expected:
        failures.append("SAVINGS_RECOMPUTE_MISMATCH")
    if not (costs["raw"] > costs["engine"] > costs["engine_costdoctor"]):
        failures.append("NO_STRICT_THREE_STAGE_NET_SAVING")
    rollback = packet.get("rollback") or {}
    for key in ("actual_status", "baseline_metrics_fingerprint", "restored_before_metrics_fingerprint", "after_metrics_fingerprint", "reapplied_after_metrics_fingerprint"):
        if not rollback.get(key):
            failures.append("ROLLBACK_PROOF_INCOMPLETE")
            break
    if rollback.get("actual_status") != "PASS" or rollback.get("baseline_metrics_fingerprint") != rollback.get("restored_before_metrics_fingerprint") or rollback.get("after_metrics_fingerprint") != rollback.get("reapplied_after_metrics_fingerprint"):
        failures.append("ROLLBACK_PROOF_FAILED")
    if packet.get("claim", {}).get("status") != "MEASURED_PENDING_INDEPENDENT_VALIDATION":
        failures.append("CLAIM_STATUS_INVALID")
    return _result(packet, failures, costs, expected, provider_actual)


def _result(packet: dict[str, Any], failures: list[str], costs: dict[str, Decimal], savings: dict[str, Any] | None = None, provider_actual: bool = False) -> dict[str, Any]:
    verdict = "PASS" if not failures else "FAIL"
    recomputed = decimal_text(costs["raw"] - costs["engine_costdoctor"]) if verdict == "PASS" and costs else None
    result = {"schema": "costdoctor.three-stage-independent-validation.v1", "verdict": verdict, "failures": sorted(set(failures)), "independent_costs": {key: decimal_text(value) for key, value in costs.items()}, "independent_savings": savings or {}, "claim_scope": packet.get("claim_scope"), "producer_digest": packet.get("producer_digest"), "independently_recomputed_savings_usd": recomputed, "verified_savings_usd": recomputed if provider_actual else None, "provider_actual_claim": provider_actual and verdict == "PASS"}
    result["validator_digest"] = sha256_json(result)
    return result


def run_false_pass_probes(packet: dict[str, Any]) -> dict[str, Any]:
    probes: dict[str, bool] = {}
    tampered = deepcopy(packet); tampered["phases"]["engine"]["binding"]["workload_fingerprint"] = "mismatch"; probes["identity_mismatch_blocked"] = validate_three_stage(tampered)["verdict"] != "PASS"
    tampered = deepcopy(packet); event = tampered["phases"]["engine_costdoctor"]["events"][0]; event["quality_score"] = 0.0; event_body = deepcopy(event); event_body.pop("event_digest", None); event["event_digest"] = sha256_json(event_body); probes["per_item_quality_loss_blocked"] = validate_three_stage(tampered)["verdict"] != "PASS"
    tampered = deepcopy(packet); event = tampered["phases"]["raw"]["events"][0]; event["measurement"] = {"grade": "PROVIDER_REPORTED_USAGE", "rank": 4}; event_body = deepcopy(event); event_body.pop("event_digest", None); event["event_digest"] = sha256_json(event_body); probes["measurement_grade_promotion_blocked"] = validate_three_stage(tampered)["verdict"] != "PASS"
    tampered = deepcopy(packet); current_grade = tampered["claim"].get("grade"); tampered["claim"]["grade"] = "NON_PROVIDER_OR_UNVERIFIED_PRICE_MEASUREMENT" if current_grade == "PROVIDER_USAGE_WITH_VERIFIED_PRICE" else "PROVIDER_USAGE_WITH_VERIFIED_PRICE"; probes["claim_grade_promotion_blocked"] = validate_three_stage(tampered)["verdict"] != "PASS"
    tampered = deepcopy(packet); tampered["phases"]["engine"]["prices"][0]["status"] = "UNKNOWN"; probes["unknown_price_blocked"] = validate_three_stage(tampered)["verdict"] != "PASS"
    tampered = deepcopy(packet); tampered["phases"]["engine_costdoctor"].pop("overhead", None); probes["overhead_omission_blocked"] = validate_three_stage(tampered)["verdict"] != "PASS"
    tampered = deepcopy(packet); tampered["phases"]["engine_costdoctor"]["net_cost_usd"] = tampered["phases"]["raw"]["net_cost_usd"]; probes["cost_up_token_down_blocked"] = validate_three_stage(tampered)["verdict"] != "PASS"
    return {"schema": "costdoctor.false-pass-probes.v1", "verdict": "PASS" if all(probes.values()) else "FAIL", "probes": probes}
