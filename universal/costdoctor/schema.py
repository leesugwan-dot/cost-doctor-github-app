from __future__ import annotations

import re
from typing import Any


class SchemaError(ValueError):
    pass


REQUIRED_EVENT_FIELDS = {
    "event_id",
    "workload_id",
    "run_id",
    "sequence",
    "provider",
    "model",
    "started_at",
    "ended_at",
    "success",
    "usage",
    "latency_ms",
    "source_binding",
    "environment_fingerprint",
    "workload_fingerprint",
}

SENSITIVE_KEYS = {
    "prompt",
    "response",
    "messages",
    "content",
    "api_key",
    "apikey",
    "authorization",
    "secret",
    "password",
    "raw_request",
    "raw_response",
}

SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN(?: [A-Z]+)? PRIVATE KEY-----"),
)


def reject_sensitive_payload(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                raise SchemaError("SENSITIVE_FIELD_REJECTED")
            reject_sensitive_payload(child)
    elif isinstance(value, list):
        for child in value:
            reject_sensitive_payload(child)
    elif isinstance(value, str):
        if any(pattern.search(value) for pattern in SECRET_PATTERNS):
            raise SchemaError("SECRET_PATTERN_REJECTED")


def validate_usage_event(event: dict[str, Any]) -> None:
    missing = REQUIRED_EVENT_FIELDS - set(event)
    if missing:
        raise SchemaError("USAGE_EVENT_REQUIRED_FIELD_MISSING")
    if not isinstance(event["sequence"], int) or event["sequence"] < 0:
        raise SchemaError("USAGE_EVENT_SEQUENCE_INVALID")
    if not isinstance(event["success"], bool):
        raise SchemaError("USAGE_EVENT_SUCCESS_INVALID")
    if not isinstance(event["usage"], dict):
        raise SchemaError("USAGE_EVENT_USAGE_INVALID")
    for key, value in event["usage"].items():
        if not isinstance(value, (int, float)) or value < 0:
            raise SchemaError("USAGE_EVENT_UNIT_INVALID")
    if not isinstance(event["latency_ms"], (int, float)) or event["latency_ms"] < 0:
        raise SchemaError("USAGE_EVENT_LATENCY_INVALID")
    binding = event["source_binding"]
    if not isinstance(binding, dict) or not binding.get("commit"):
        raise SchemaError("USAGE_EVENT_SOURCE_BINDING_INVALID")
