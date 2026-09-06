from __future__ import annotations

from typing import Any


MEASUREMENT_GRADES = {
    "UNKNOWN": 0,
    "BYTE_PROXY": 1,
    "AVAILABLE_TOOL_USAGE": 2,
    "EXACT_TOKENIZER": 3,
    "PROVIDER_REPORTED_USAGE": 4,
}


def classify_measurement(payload: dict[str, Any]) -> dict[str, Any]:
    """Classify usage without promoting self-declared counters to provider usage."""
    source = str(payload.get("measurement_source", "")).upper()
    provider_reported = payload.get("provider_reported") is True
    provider_response_id = str(payload.get("provider_response_id", "")).strip()
    tokenizer = payload.get("tokenizer") or {}

    if provider_reported and provider_response_id and source in {
        "PROVIDER_RESPONSE",
        "PROVIDER_USAGE_EXPORT",
        "CUSTOMER_PROVIDER_RECEIPT",
    }:
        grade = "PROVIDER_REPORTED_USAGE"
        reason = "usage counters are bound to a provider response identifier"
    elif source == "EXACT_TOKENIZER" and tokenizer.get("name") and tokenizer.get("version"):
        grade = "EXACT_TOKENIZER"
        reason = "usage was counted by an identified tokenizer"
    elif source in {"CODEX_AVAILABLE_USAGE", "CLAUDE_CODE_AVAILABLE_USAGE", "AVAILABLE_TOOL_USAGE"}:
        grade = "AVAILABLE_TOOL_USAGE"
        reason = "the coding tool exposed counters, but provider billing authenticity is not asserted"
    elif source in {"BYTE_PROXY", "LOCAL_DETERMINISTIC_ACTUAL_RUN", "ARITHMETIC_PROXY"}:
        grade = "BYTE_PROXY"
        reason = "the workload ran, but token usage is derived from bytes or arithmetic"
    else:
        grade = "UNKNOWN"
        reason = "no admissible usage measurement provenance was supplied"

    return {
        "grade": grade,
        "rank": MEASUREMENT_GRADES[grade],
        "reason": reason,
        "actual_provider_usage": grade == "PROVIDER_REPORTED_USAGE",
        "provider_authenticated": False,
    }


def weakest_measurement(events: list[dict[str, Any]]) -> dict[str, Any]:
    if not events:
        return {"grade": "UNKNOWN", "rank": 0, "reason": "no events"}
    measurements = [event.get("measurement") or classify_measurement(event) for event in events]
    weakest = min(measurements, key=lambda item: int(item.get("rank", 0)))
    return {
        "grade": weakest["grade"],
        "rank": int(weakest.get("rank", 0)),
        "event_grades": sorted({str(item.get("grade", "UNKNOWN")) for item in measurements}),
        "actual_provider_usage": all(item.get("actual_provider_usage") is True for item in measurements),
    }


def assert_no_grade_promotion(event: dict[str, Any]) -> bool:
    claimed = event.get("measurement") or {}
    observed = classify_measurement(event)
    return claimed.get("grade") == observed["grade"] and int(claimed.get("rank", -1)) == observed["rank"]
