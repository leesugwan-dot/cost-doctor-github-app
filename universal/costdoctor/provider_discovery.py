from __future__ import annotations

"""Registry-driven provider/model discovery for runner-local target scans.

The detector emits only aggregate, sanitized evidence. Provider names, secret
labels, endpoint hints, and model aliases come from registry data; the core
does not contain a provider-specific decision table.
"""

import json
import re
from pathlib import Path
from typing import Any


EXCLUDED = {".git", ".hg", ".svn", "node_modules", "dist", "build", ".venv", "venv", "__pycache__", ".cache"}
TEXT_SUFFIXES = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".json", ".yml", ".yaml", ".md", ".toml", ".ini", ".txt", ".go", ".java", ".rb", ".rs", ".sh"}


def _rows(directory: Path, prefix: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not str(payload.get("schema", "")).startswith(prefix):
            continue
        result.extend(row for row in payload.get("rows", []) if isinstance(row, dict))
    return result


def _iter_text(repo: Path):
    for path in repo.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in EXCLUDED for part in path.relative_to(repo).parts):
            continue
        try:
            yield path.read_text(encoding="utf-8", errors="ignore")[:2_000_000]
        except OSError:
            continue


def _terms(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def discover(repo: Path, registry_root: Path) -> dict[str, Any]:
    providers = _rows(registry_root / "providers", "costdoctor.provider-registry.")
    models = _rows(registry_root / "models", "costdoctor.model-registry.")
    texts = list(_iter_text(repo))
    joined = "\n".join(texts)
    candidates: list[dict[str, Any]] = []
    for row in providers:
        detection = row.get("detection") or {}
        positive = _terms(detection.get("terms"))
        endpoints = _terms(detection.get("endpoint_terms"))
        secrets = _terms(row.get("secret_names"))
        score = sum(len(re.findall(re.escape(term), joined, flags=re.IGNORECASE)) for term in positive)
        score += 2 * sum(len(re.findall(re.escape(term), joined, flags=re.IGNORECASE)) for term in endpoints)
        score += 3 * sum(len(re.findall(re.escape(term), joined, flags=re.IGNORECASE)) for term in secrets)
        if detection.get("always_for_local") and any(term.lower() in joined.lower() for term in positive):
            score += 1
        if score <= 0:
            continue
        model_patterns = detection.get("model_patterns") or {}
        model_candidates: list[tuple[int, str]] = []
        for model_id, patterns in model_patterns.items():
            hits = sum(len(re.findall(re.escape(term), joined, flags=re.IGNORECASE)) for term in _terms(patterns))
            if hits:
                model_candidates.append((hits, str(model_id)))
        model_candidates.sort(reverse=True)
        model = model_candidates[0][1] if model_candidates else None
        candidates.append({
            "provider": str(row.get("provider")),
            "adapter": str(row.get("adapter")),
            "score": score,
            "model": model,
            "credential_name": (secrets[0] if secrets else None),
            "base_url": row.get("default_base_url"),
            "capabilities": row.get("capabilities") or {},
        })
    candidates.sort(key=lambda item: (-int(item["score"]), item["provider"]))
    selected = candidates[0] if candidates else None
    if selected and not selected.get("model"):
        provider_models = [row for row in models if row.get("provider") == selected["provider"] and row.get("status") in {"active", "preview"}]
        if len(provider_models) == 1:
            selected["model"] = provider_models[0].get("canonical_id")
    if selected:
        contract = {
            "provider": selected["provider"],
            "adapter": selected["adapter"],
            "model": selected.get("model"),
            "credential_name": selected.get("credential_name"),
            "base_url": selected.get("base_url"),
            "secret_source_required": "TARGET_REPOSITORY_GITHUB_SECRET" if selected.get("credential_name") else "NONE",
        }
        status = "DETECTED"
    else:
        contract = {"provider": None, "adapter": "generic_v1", "model": None, "credential_name": None, "base_url": None, "secret_source_required": "NONE"}
        status = "UNKNOWN_PROVIDER"
    return {
        "status": status,
        "provider_candidates": [{key: item[key] for key in ("provider", "adapter", "score", "model", "credential_name", "base_url")} for item in candidates],
        "selected": contract,
        "registry_rows_considered": len(providers),
        "model_rows_considered": len(models),
        "text_units_scanned": len(texts),
    }


def stage2_level(discovery: dict[str, Any], *, workload_ready: bool, deterministic_measurement: bool = False, priced: bool = False, provider_usage: bool = False) -> str:
    if provider_usage:
        return "L5_VERIFIED_SAVINGS"
    if priced and deterministic_measurement:
        return "L3_ESTIMATED_COST_SAVINGS"
    if deterministic_measurement:
        return "L2_DETERMINISTIC_MEASUREMENT"
    if discovery.get("status") == "DETECTED" or workload_ready:
        return "L1_STRUCTURAL_DIAGNOSIS"
    return "L1_STRUCTURAL_DIAGNOSIS" if discovery.get("status") == "UNKNOWN_PROVIDER" else "L0_STATIC_SIGNAL"
