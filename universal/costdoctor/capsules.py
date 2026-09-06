from __future__ import annotations

from copy import deepcopy
from typing import Any

from .canonical import sha256_json
from .schema import reject_sensitive_payload


CAPSULE_REQUIRED_FIELDS = {
    "task": {"task_id", "objective", "acceptance", "allowed_scope", "forbidden_scope", "target_files", "output_contract"},
    "state": {"completed", "pending", "current_authority", "current_version", "blockers", "next_action"},
    "context": {"required_facts", "selected_context", "omitted_context_reason", "token_budget", "retention_check"},
    "evidence": {"run_id", "workload_id", "metrics", "quality", "errors", "hashes", "pointers", "verifier_result"},
    "delta": {"changed_facts", "changed_files", "changed_decisions", "invalidated_evidence", "new_requirements"},
    "usage": {"provider", "model", "input", "cached", "output", "reasoning", "calls", "retries", "cost", "measurement_grade"},
}


class CapsuleError(ValueError):
    pass


def build_capsule(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    required = CAPSULE_REQUIRED_FIELDS.get(kind)
    if required is None:
        raise CapsuleError("CAPSULE_KIND_UNKNOWN")
    missing = sorted(required - set(payload))
    if missing:
        raise CapsuleError("CAPSULE_REQUIRED_FIELD_MISSING:" + ",".join(missing))
    reject_sensitive_payload(payload)
    body = deepcopy(payload)
    result = {"schema": f"costdoctor.{kind}-capsule.v1", **body}
    result["capsule_fingerprint"] = sha256_json(result)
    return result


def verify_capsule(capsule: dict[str, Any]) -> bool:
    schema = str(capsule.get("schema", ""))
    if not schema.startswith("costdoctor.") or not schema.endswith("-capsule.v1"):
        return False
    kind = schema.removeprefix("costdoctor.").removesuffix("-capsule.v1")
    if kind not in CAPSULE_REQUIRED_FIELDS:
        return False
    claimed = capsule.get("capsule_fingerprint")
    body = deepcopy(capsule)
    body.pop("capsule_fingerprint", None)
    return claimed == sha256_json(body) and not (CAPSULE_REQUIRED_FIELDS[kind] - set(capsule))
