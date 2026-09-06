from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from .canonical import canonical_json, sha256_json
from .capsules import build_capsule


class ContextOptimizationError(ValueError):
    pass


def _byte_size(value: Any) -> int:
    return len(canonical_json(value).encode("utf-8"))


def _measure(value: Any, tokenizer: Callable[[str], int] | None) -> tuple[int, str]:
    serialized = canonical_json(value)
    if tokenizer is not None:
        count = int(tokenizer(serialized))
        if count < 0:
            raise ContextOptimizationError("TOKENIZER_COUNT_INVALID")
        return count, "EXACT_TOKENIZER"
    return max(1, len(serialized.encode("utf-8")) // 4), "BYTE_PROXY"


def _authority_resolve(entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        key = str(entry.get("authority_key") or entry["id"])
        grouped.setdefault(key, []).append(deepcopy(entry))
    selected: list[dict[str, Any]] = []
    superseded: list[str] = []
    for key in sorted(grouped):
        rows = sorted(
            grouped[key],
            key=lambda row: (int(row.get("authority_rank", 0)), int(row.get("version", 0)), str(row["id"])),
            reverse=True,
        )
        selected.append(rows[0])
        superseded.extend(str(row["id"]) for row in rows[1:])
    return selected, sorted(superseded)


def extract_facts(entries: list[dict[str, Any]], required_fact_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """Normalize structured facts without inventing facts from untrusted raw prose."""
    required = {str(item) for item in (required_fact_ids or [])}
    result = []
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("id"):
            raise ContextOptimizationError("CONTEXT_ENTRY_INVALID")
        row = deepcopy(entry)
        fact_id = str(row.get("fact_id") or row["id"])
        row["fact_id"] = fact_id
        row["hard_fact"] = bool(row.get("required", False) or fact_id in required)
        result.append(row)
    return result


def resolve_authority(entries: list[dict[str, Any]]) -> dict[str, Any]:
    selected, superseded = _authority_resolve(entries)
    return {"selected": selected, "superseded_ids": superseded}


def build_delta(selected_context: list[dict[str, Any]], previous_context: dict[str, Any] | None = None) -> dict[str, Any]:
    previous_hashes = {str(row["id"]): sha256_json(row) for row in (previous_context or {}).get("selected_context", []) if isinstance(row, dict) and row.get("id")}
    selected_hashes = {str(row["id"]): sha256_json(row) for row in selected_context}
    return {"changed_ids": sorted(row_id for row_id, digest in selected_hashes.items() if previous_hashes.get(row_id) != digest), "removed_ids": sorted(set(previous_hashes) - set(selected_hashes))}


def _runtime_entry(entry: dict[str, Any]) -> dict[str, Any]:
    if entry.get("kind") == "evidence":
        pointer = entry.get("pointer") or {}
        if not pointer.get("sha256") or not pointer.get("locator"):
            raise ContextOptimizationError("EVIDENCE_POINTER_INCOMPLETE")
        return {
            "id": str(entry["id"]),
            "fact_id": str(entry.get("fact_id") or entry["id"]),
            "kind": "evidence_pointer",
            "pointer": {"sha256": str(pointer["sha256"]), "locator": str(pointer["locator"]), "count": int(pointer.get("count", 1))},
            "required": bool(entry.get("required", False)),
            "priority": int(entry.get("priority", 0)),
        }
    return {
        "id": str(entry["id"]), "fact_id": str(entry.get("fact_id") or entry["id"]),
        "kind": str(entry.get("kind", "fact")), "value": deepcopy(entry.get("value")),
        "required": bool(entry.get("required", False)), "priority": int(entry.get("priority", 0)),
    }


def optimize_context(task: dict[str, Any], state: dict[str, Any], entries: list[dict[str, Any]], token_budget: int, previous_context: dict[str, Any] | None = None, tokenizer: Callable[[str], int] | None = None) -> dict[str, Any]:
    if token_budget <= 0:
        raise ContextOptimizationError("CONTEXT_BUDGET_INVALID")
    if not entries:
        raise ContextOptimizationError("CONTEXT_ENTRY_INVALID")
    facts = extract_facts(entries, [str(item) for item in task.get("required_fact_ids", [])])
    authoritative, superseded = _authority_resolve(facts)
    rows = [_runtime_entry(entry) for entry in authoritative]
    required_ids = {str(item) for item in task.get("required_fact_ids", [])}
    required_ids.update(row["fact_id"] for row in rows if row["required"])
    rows.sort(key=lambda row: (row["fact_id"] not in required_ids, -row["priority"], row["id"]))
    selected: list[dict[str, Any]] = []
    omitted: dict[str, str] = {item: "superseded_by_higher_authority" for item in superseded}
    used = 0
    measurement_grade = "BYTE_PROXY"
    for row in rows:
        size, grade = _measure(row, tokenizer)
        measurement_grade = grade
        required = row["fact_id"] in required_ids
        if used + size <= token_budget:
            selected.append(row)
            used += size
        elif required:
            raise ContextOptimizationError("LOSS_GUARD_REQUIRED_FACT_BUDGET_EXCEEDED")
        else:
            omitted[row["id"]] = "lower_priority_than_budget"
    retained = {row["fact_id"] for row in selected}
    missing = sorted(required_ids - retained)
    if missing:
        raise ContextOptimizationError("LOSS_GUARD_REQUIRED_FACT_MISSING:" + ",".join(missing))
    delta = build_delta(selected, previous_context)
    capsule = build_capsule("context", {"required_facts": sorted(required_ids), "selected_context": selected, "omitted_context_reason": omitted, "token_budget": {"limit": token_budget, "used": used, "measurement_grade": measurement_grade}, "retention_check": {"verdict": "PASS", "required_count": len(required_ids), "retained_count": len(required_ids), "missing": []}})
    capsule["authority_resolution"] = {"superseded_ids": superseded, "selected_count": len(authoritative)}
    capsule["delta"] = delta
    capsule["task_fingerprint"] = sha256_json(task)
    capsule["state_fingerprint"] = sha256_json(state)
    fingerprint_body = deepcopy(capsule)
    fingerprint_body.pop("capsule_fingerprint", None)
    capsule["capsule_fingerprint"] = sha256_json(fingerprint_body)
    return capsule


def context_size_receipt(raw_entries: list[dict[str, Any]], optimized: dict[str, Any]) -> dict[str, Any]:
    raw_bytes = _byte_size(raw_entries)
    optimized_bytes = _byte_size(optimized.get("selected_context", []))
    return {"raw_bytes": raw_bytes, "optimized_bytes": optimized_bytes, "byte_reduction_fraction": round((raw_bytes - optimized_bytes) / raw_bytes, 9) if raw_bytes else 0, "measurement_grade": "BYTE_CONTEXT_ONLY", "token_savings_claimed": False}
