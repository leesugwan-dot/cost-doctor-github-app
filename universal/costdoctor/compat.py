from __future__ import annotations

from copy import deepcopy
from typing import Any


def read_report(payload: dict[str, Any]) -> dict[str, Any]:
    schema = payload.get("schema")
    if schema == "costdoctor.repository-entry.v1":
        return {
            "schema": "costdoctor.report-envelope.v2",
            "source_schema": schema,
            "legacy_report": deepcopy(payload),
            "runtime_evidence": None,
            "verified_savings": None,
            "compatibility": "BACKWARD_COMPATIBLE_V1",
        }
    if schema == "costdoctor.report-envelope.v2":
        return deepcopy(payload)
    return {
        "schema": "costdoctor.report-envelope.v2",
        "source_schema": schema or "unknown",
        "legacy_report": deepcopy(payload),
        "runtime_evidence": None,
        "verified_savings": None,
        "compatibility": "UNKNOWN_FIELDS_PRESERVED",
    }
