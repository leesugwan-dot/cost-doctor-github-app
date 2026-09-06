from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .canonical import decimal_text, parse_time, sha256_json, utc_now


VALIDATOR_VERSION = "costdoctor-independent-validator-1.0.0"
TOKEN_UNITS = ("input_tokens", "output_tokens", "cached_input_tokens", "cache_write_tokens", "reasoning_tokens")


def _independent_price(event: dict[str, Any], price: dict[str, Any]) -> tuple[str, str | None]:
    snapshot = deepcopy(price.get("pricing_snapshot"))
    if price.get("status") == "UNKNOWN" or not snapshot:
        return "UNKNOWN", None
    claimed_snapshot_digest = snapshot.pop("snapshot_digest", None)
    if claimed_snapshot_digest != sha256_json(snapshot):
        return "TAMPERED_PRICE_SNAPSHOT", None
    rates = snapshot.get("unit_rates_usd") or {}
    total = Decimal("0")
    for unit in TOKEN_UNITS:
        quantity = Decimal(str(event["usage"].get(unit, 0)))
        if quantity:
            if rates.get(unit) is None:
                return "UNKNOWN", None
            total += quantity * Decimal(str(rates[unit])) / Decimal("1000000")
    tool_calls = Decimal(str(event["usage"].get("tool_calls", 0)))
    if tool_calls:
        if rates.get("tool_calls") is None:
            return "UNKNOWN", None
        total += tool_calls * Decimal(str(rates["tool_calls"]))
    for unit, quantity_value in (event.get("billed_units") or {}).items():
        quantity = Decimal(str(quantity_value))
        rate = (snapshot.get("custom_unit_rates_usd") or {}).get(unit)
        if quantity and rate is None:
            return "UNKNOWN", None
        if quantity:
            total += quantity * Decimal(str(rate))
    if event.get("batch"):
        discount = Decimal(str(snapshot.get("batch_discount_fraction", 0)))
        if discount < 0 or discount >= 1:
            return "PRICE_RULE_INVALID", None
        total *= Decimal("1") - discount
    total = max(total, Decimal(str(snapshot.get("request_minimum_usd", 0))))
    quantum = Decimal(1).scaleb(-int(snapshot.get("rounding_decimals", 9)))
    total = total.quantize(quantum, rounding=ROUND_HALF_UP)
    return "KNOWN", decimal_text(total)


def validate_packet(packet: dict[str, Any], max_age_seconds: int = 3600) -> dict[str, Any]:
    failures: list[str] = []
    if packet.get("schema") != "costdoctor.benchmark-evidence.v1":
        failures.append("SCHEMA_INVALID")
    digest_target = deepcopy(packet)
    claimed_digest = digest_target.pop("producer_digest", None)
    digest_target.pop("independent_validation", None)
    if claimed_digest != sha256_json(digest_target):
        failures.append("PRODUCER_DIGEST_MISMATCH")
    try:
        age = (datetime.now(timezone.utc) - parse_time(str(packet["generated_at"]))).total_seconds()
        if age < -60 or age > max_age_seconds:
            failures.append("EVIDENCE_NOT_FRESH")
    except (KeyError, ValueError):
        failures.append("EVIDENCE_TIME_INVALID")

    comparison = packet.get("bindings", {}).get("comparison", {})
    if comparison.get("verdict") != "PASS" or comparison.get("mismatches"):
        failures.append("BINDING_COMPARISON_FAILED")
    before_binding = packet.get("bindings", {}).get("before", {})
    after_binding = packet.get("bindings", {}).get("after", {})
    if before_binding != after_binding:
        failures.append("BEFORE_AFTER_BINDING_MISMATCH")

    phase_totals: dict[str, Decimal] = {}
    unknown_price = False
    for phase_name in ("before", "after"):
        phase = packet.get(phase_name, {})
        events = phase.get("events", [])
        prices = {price.get("event_id"): price for price in phase.get("prices", [])}
        total = Decimal("0")
        for event in events:
            binding = before_binding if phase_name == "before" else after_binding
            if event.get("source_binding", {}).get("commit") != binding.get("commit"):
                failures.append(f"{phase_name.upper()}_COMMIT_BINDING_MISMATCH")
            if event.get("workload_fingerprint") != binding.get("workload_fingerprint"):
                failures.append(f"{phase_name.upper()}_WORKLOAD_BINDING_MISMATCH")
            event_copy = deepcopy(event)
            claimed_event_digest = event_copy.pop("event_digest", None)
            if claimed_event_digest != sha256_json(event_copy):
                failures.append(f"{phase_name.upper()}_EVENT_DIGEST_MISMATCH")
            price = prices.get(event.get("event_id"), {})
            status, calculated = _independent_price(event, price)
            if status == "UNKNOWN":
                unknown_price = True
                continue
            if status != "KNOWN" or calculated != price.get("cost_usd"):
                failures.append(f"{phase_name.upper()}_PRICE_RECOMPUTE_MISMATCH")
                continue
            total += Decimal(calculated)
        phase_totals[phase_name] = total
        metrics_total = phase.get("metrics", {}).get("total_cost_usd")
        if not unknown_price and metrics_total is not None and Decimal(str(metrics_total)) != total:
            failures.append(f"{phase_name.upper()}_METRICS_COST_MISMATCH")

    quality = packet.get("quality", {})
    if quality.get("verdict") != "PASS":
        failures.append("QUALITY_GATE_FAILED")
    elif quality.get("after_mean", 0) < quality.get("threshold", 1):
        failures.append("QUALITY_THRESHOLD_MISMATCH")
    elif quality.get("after_mean", 0) + quality.get("allowed_regression", 0) < quality.get("before_mean", 0):
        failures.append("QUALITY_REGRESSION")

    rollback = packet.get("rollback", {})
    if rollback.get("actual_status") != "PASS":
        failures.append("ROLLBACK_ACTUAL_MISSING")
    if rollback.get("restored_before_metrics_fingerprint") != rollback.get("baseline_metrics_fingerprint"):
        failures.append("ROLLBACK_BASELINE_MISMATCH")
    if rollback.get("reapplied_after_metrics_fingerprint") != rollback.get("after_metrics_fingerprint"):
        failures.append("REAPPLY_AFTER_MISMATCH")

    claim = packet.get("claim", {})
    measured = claim.get("measured_savings_usd")
    independently_calculated = phase_totals.get("before", Decimal("0")) - phase_totals.get("after", Decimal("0"))
    if unknown_price:
        if claim.get("status") != "UNKNOWN" or claim.get("verified_savings_usd") is not None:
            failures.append("UNKNOWN_PRICE_CLAIM_NOT_BLOCKED")
        verdict = "BLOCKED" if not failures else "FAIL"
        verified = None
    else:
        if claim.get("status") != "MEASURED_PENDING_INDEPENDENT_VALIDATION":
            failures.append("CLAIM_STATUS_INVALID")
        if measured is None or Decimal(str(measured)) != independently_calculated or independently_calculated <= 0:
            failures.append("SAVINGS_RECOMPUTE_MISMATCH")
        verdict = "PASS" if not failures else "FAIL"
        verified = decimal_text(independently_calculated) if verdict == "PASS" else None

    result = {
        "schema": "costdoctor.independent-validation.v1",
        "validator": VALIDATOR_VERSION,
        "validated_at": utc_now(),
        "verdict": verdict,
        "failures": sorted(set(failures)),
        "verified_savings_usd": verified,
        "claim_level": 5 if verdict == "PASS" else None,
        "claim_scope": packet.get("claim_scope"),
        "producer_digest": packet.get("producer_digest"),
        "independent_costs": {key: decimal_text(value) for key, value in phase_totals.items()},
    }
    result["validator_digest"] = sha256_json(result)
    return result
