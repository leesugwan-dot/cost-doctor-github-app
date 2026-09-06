from __future__ import annotations

import re
from decimal import Decimal
from html.parser import HTMLParser
from typing import Any

from .canonical import decimal_text, sha256_bytes, sha256_json, utc_now


ALLOWED_APPLICATION_STATES = {
    "APPLIED_AND_VERIFIED",
    "PROPOSED_ONLY",
    "APPLY_FAILED",
    "ROLLED_BACK",
    "NOT_APPLICABLE",
}
ALLOWED_TRUST_LEVELS = {
    "VERIFIED",
    "MEASURED",
    "ESTIMATED",
    "BILLING_CONFIRMED",
    "STATIC_SIGNAL",
    "UNKNOWN",
    "BLOCKED",
}
CORE_FIELDS = (
    "verdict",
    "trust_level",
    "application_state",
    "before_cost_usd",
    "after_cost_usd",
    "verified_savings_usd",
    "savings_rate_percent",
    "quality_before",
    "quality_after",
    "quality_verdict",
    "rollback_status",
    "pricing_status_before",
    "pricing_status_after",
    "independent_validation",
)


class _FactParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.values: dict[str, list[str]] = {}
        self.stack: list[tuple[str, str, list[str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        field = dict(attrs).get("data-field")
        if field:
            self.stack.append((tag, field, []))

    def handle_data(self, data: str) -> None:
        if self.stack:
            self.stack[-1][2].append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.stack and self.stack[-1][0] == tag:
            _, field, chunks = self.stack.pop()
            self.values.setdefault(field, []).append("".join(chunks).strip())


def _shown(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    if isinstance(value, float):
        return format(value, ".9g")
    return str(value)


def _expected_verdict(packet: dict[str, Any], validation: dict[str, Any]) -> str:
    claim = packet.get("claim", {}).get("status")
    quality = packet.get("quality", {}).get("verdict")
    if claim == "NO_SAVINGS":
        return "NO_SAVINGS"
    if claim in {"UNKNOWN", "BLOCKED", "INCONCLUSIVE"}:
        return "BLOCKED"
    if quality == "FAIL":
        return "FAIL"
    if quality == "NEEDS_EVIDENCE" or validation.get("verdict") == "NEEDS_EVIDENCE":
        return "NEEDS_EVIDENCE"
    if validation.get("verdict") == "PASS" and validation.get("verified_savings_usd") is not None:
        return "PASS"
    if validation.get("verdict") == "FAIL":
        return "FAIL"
    return "BLOCKED"


def _expected_trust(packet: dict[str, Any], validation: dict[str, Any]) -> str:
    claim = packet.get("claim", {}).get("status")
    if validation.get("verdict") == "PASS" and validation.get("verified_savings_usd") is not None:
        return "VERIFIED"
    if claim == "MEASURED_PENDING_INDEPENDENT_VALIDATION":
        return "MEASURED"
    if claim == "UNKNOWN":
        return "UNKNOWN"
    if validation.get("verdict") in {"FAIL", "BLOCKED"}:
        return "BLOCKED"
    if packet.get("detectors"):
        return "STATIC_SIGNAL"
    return "UNKNOWN"


def _expected_application(packet: dict[str, Any], validation: dict[str, Any]) -> str:
    claim = packet.get("claim", {}).get("status")
    if validation.get("verdict") == "PASS" and packet.get("rollback", {}).get("actual_status") == "PASS":
        return "APPLIED_AND_VERIFIED"
    if claim == "NO_SAVINGS" and packet.get("rollback", {}).get("actual_status") == "PASS":
        return "ROLLED_BACK"
    if packet.get("quality", {}).get("verdict") == "FAIL":
        return "APPLY_FAILED"
    return "NOT_APPLICABLE"


def _expected_facts(
    packet: dict[str, Any], validation: dict[str, Any], application_state: str | None
) -> dict[str, Any]:
    before = packet.get("before", {}).get("metrics", {})
    after = packet.get("after", {}).get("metrics", {})
    quality = packet.get("quality", {})
    verified = validation.get("verified_savings_usd") if validation.get("verdict") == "PASS" else None
    before_cost = before.get("total_cost_usd")
    rate = None
    if verified is not None and before_cost is not None and Decimal(str(before_cost)) > 0:
        rate = decimal_text(Decimal(str(verified)) * Decimal("100") / Decimal(str(before_cost)))
    return {
        "verdict": _expected_verdict(packet, validation),
        "trust_level": _expected_trust(packet, validation),
        "application_state": application_state or _expected_application(packet, validation),
        "before_cost_usd": before_cost,
        "after_cost_usd": after.get("total_cost_usd"),
        "verified_savings_usd": verified,
        "savings_rate_percent": rate,
        "quality_before": quality.get("before_mean"),
        "quality_after": quality.get("after_mean"),
        "quality_verdict": quality.get("verdict", "NEEDS_EVIDENCE"),
        "rollback_status": packet.get("rollback", {}).get("actual_status", "UNKNOWN"),
        "pricing_status_before": before.get("pricing_status", "UNKNOWN"),
        "pricing_status_after": after.get("pricing_status", "UNKNOWN"),
        "independent_validation": validation.get("verdict", "NEEDS_EVIDENCE"),
    }


def _html_facts(raw: str) -> dict[str, list[str]]:
    parser = _FactParser()
    parser.feed(raw)
    parser.close()
    return parser.values


def _leaks(raw: str) -> list[str]:
    patterns = {
        "WINDOWS_PATH": r"[A-Za-z]:[\\/][^\s<>]+",
        "LOCAL_UNIX_PATH": r"/(?:home|Users|tmp|var/tmp)/[^\s<>]+",
        "HASH": r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{64}(?![0-9A-Fa-f])",
        "INTERNAL_FILENAME": r"\b[\w.-]+\.(?:json|jsonl|py|mjs|ya?ml)\b",
        "SECRET": r"(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{12,}|api[_-]?key\s*[:=])",
        "RAW_JSON": r"\{\s*\"[A-Za-z0-9_-]+\"\s*:",
    }
    return [name for name, pattern in patterns.items() if re.search(pattern, raw, re.IGNORECASE)]


def validate_user_report(
    packet: dict[str, Any],
    validation: dict[str, Any],
    report: dict[str, Any],
    easy_html: str,
    print_html: str,
    *,
    expected_application_state: str | None = None,
    regenerated_report: dict[str, Any] | None = None,
    regenerated_easy_html: str | None = None,
    regenerated_print_html: str | None = None,
) -> dict[str, Any]:
    failures: list[str] = []
    if report.get("schema") != "costdoctor.user-report.v1":
        failures.append("REPORT_SCHEMA_INVALID")
    if expected_application_state is not None and expected_application_state not in ALLOWED_APPLICATION_STATES:
        failures.append("EXPECTED_APPLICATION_STATE_INVALID")
    expected = _expected_facts(packet, validation, expected_application_state)
    actual = report.get("facts", {})
    for field in CORE_FIELDS:
        if actual.get(field) != expected.get(field):
            failures.append(f"REPORT_FACT_MISMATCH:{field}")
    if actual.get("trust_level") not in ALLOWED_TRUST_LEVELS:
        failures.append("TRUST_LEVEL_INVALID")
    if actual.get("application_state") not in ALLOWED_APPLICATION_STATES:
        failures.append("APPLICATION_STATE_INVALID")
    if actual.get("trust_level") == "BILLING_CONFIRMED":
        all_events = packet.get("before", {}).get("events", []) + packet.get("after", {}).get("events", [])
        if not all_events or not all(event.get("provider_reported") for event in all_events):
            failures.append("BILLING_CONFIRMED_WITHOUT_PROVIDER_EVIDENCE")
    if packet.get("claim", {}).get("status") == "UNKNOWN" and actual.get("verified_savings_usd") is not None:
        failures.append("UNKNOWN_PRICE_EXPOSED_AS_SAVINGS")

    html_results = {}
    for name, raw in (("easy", easy_html), ("print", print_html)):
        parsed = _html_facts(raw)
        html_results[name] = parsed
        for field in CORE_FIELDS:
            values = parsed.get(field, [])
            expected_text = _shown(expected.get(field))
            if not values or any(value != expected_text for value in values):
                failures.append(f"{name.upper()}_HTML_FACT_MISMATCH:{field}")
        for leak in _leaks(raw):
            failures.append(f"{name.upper()}_DEFAULT_VIEW_LEAK:{leak}")

    rendered_equivalent = all(
        html_results["easy"].get(field) == html_results["print"].get(field)
        for field in CORE_FIELDS
    )
    if not rendered_equivalent:
        failures.append("EASY_PRINT_FACT_DIVERGENCE")
    if regenerated_report is not None and sha256_json(report) != sha256_json(regenerated_report):
        failures.append("REPORT_REGENERATION_MISMATCH")
    if regenerated_easy_html is not None and sha256_bytes(easy_html.encode("utf-8")) != sha256_bytes(regenerated_easy_html.encode("utf-8")):
        failures.append("EASY_HTML_REGENERATION_MISMATCH")
    if regenerated_print_html is not None and sha256_bytes(print_html.encode("utf-8")) != sha256_bytes(regenerated_print_html.encode("utf-8")):
        failures.append("PRINT_HTML_REGENERATION_MISMATCH")

    result = {
        "schema": "costdoctor.user-report-independent-validation.v1",
        "validated_at": utc_now(),
        "source_recomputation": "PASS" if not any(item.startswith("REPORT_FACT_MISMATCH") for item in failures) else "FAIL",
        "visible_fact_parity": "PASS" if not any("HTML_FACT_MISMATCH" in item or item == "EASY_PRINT_FACT_DIVERGENCE" for item in failures) else "FAIL",
        "user_view_sanitized": "PASS" if not any("DEFAULT_VIEW_LEAK" in item for item in failures) else "FAIL",
        "deterministic_regeneration": "PASS" if not any("REGENERATION_MISMATCH" in item for item in failures) else "FAIL",
        "expected_user_verdict": expected["verdict"],
        "expected_trust_level": expected["trust_level"],
        "expected_application_state": expected["application_state"],
        "failures": sorted(set(failures)),
        "verdict": "PASS" if not failures else "FAIL",
    }
    result["validator_digest"] = sha256_json(result)
    return result
