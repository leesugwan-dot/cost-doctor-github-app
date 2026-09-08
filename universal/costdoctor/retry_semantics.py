"""Offline retry layer semantics used by fixture validation."""
from __future__ import annotations

from typing import Any


def normalize_retry_layers(layers: list[dict[str, Any]]) -> dict[str, Any]:
    total = 1
    unknown = []
    normalized = []
    for index, row in enumerate(layers):
        kind = str(row.get("kind") or "unknown")
        value = row.get("value")
        if value is None:
            unknown.append(index)
            normalized.append({"layer": index, "kind": kind, "semantics": "UNKNOWN", "value": None})
            continue
        value = int(value)
        if value < 0:
            unknown.append(index)
            normalized.append({"layer": index, "kind": kind, "semantics": "INVALID", "value": value})
            continue
        if kind == "stop_after_attempt":
            attempts = value
            total *= max(1, attempts)
            normalized.append({"layer": index, "kind": kind, "semantics": "TOTAL_ATTEMPTS", "value": value, "attempts_upper_bound": attempts})
        elif kind in {"max_retries", "maxRetries", "retries"}:
            total *= 1 + value
            normalized.append({"layer": index, "kind": kind, "semantics": "ADDITIONAL_RETRIES", "value": value, "attempts_upper_bound": 1 + value})
        elif kind == "disabled":
            normalized.append({"layer": index, "kind": kind, "semantics": "DISABLED", "value": value, "attempts_upper_bound": 1})
        else:
            unknown.append(index)
            normalized.append({"layer": index, "kind": kind, "semantics": "UNKNOWN", "value": value})
    return {"status": "UNKNOWN" if unknown else "PASS", "total_attempts_upper_bound": None if unknown else total, "unknown_layers": unknown, "layers": normalized}
