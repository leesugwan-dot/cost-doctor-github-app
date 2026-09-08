from __future__ import annotations

"""Registry-driven provider contract discovery for runner-local scans.

The transport client (for example an OpenAI-compatible SDK) is deliberately
kept separate from the service that owns the endpoint, model, credential and
price. Identity is resolved from registry evidence in this order:
endpoint -> explicit model -> provider credential -> SDK/import -> generic
terms. Only aggregate, sanitized evidence leaves the runner.
"""

import json
import re
from pathlib import Path
from typing import Any


EXCLUDED = {".git", ".hg", ".svn", "node_modules", "dist", "build", ".venv", "venv", "__pycache__", ".cache"}
TEXT_SUFFIXES = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".json", ".yml", ".yaml", ".md", ".toml", ".ini", ".txt", ".go", ".java", ".rb", ".rs", ".sh"}
MAX_DISCOVERY_FILE_BYTES = 500_000
SENSITIVE_NAME = re.compile(r"(?i)^(?:\.env(?:\..*)?|credentials?|secrets?|tokens?|private.?key|.*\.(?:pem|key))$")
_CONFIDENCE_RANK = {"STRONG": 3, "MEDIUM": 2, "WEAK": 1, "NONE": 0}


def _rows(directory: Path, prefix: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if not directory.is_dir():
        return result
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not str(payload.get("schema", "")).startswith(prefix):
            continue
        result.extend(row for row in payload.get("rows", []) if isinstance(row, dict))
    return result


def _iter_text(repo: Path):
    try:
        paths = sorted(repo.rglob("*"), key=lambda item: str(item.relative_to(repo)).lower())
    except OSError:
        paths = []
    for path in paths:
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in EXCLUDED for part in path.relative_to(repo).parts) or SENSITIVE_NAME.search(path.name):
            continue
        try:
            with path.open("rb") as handle:
                raw = handle.read(MAX_DISCOVERY_FILE_BYTES + 1)
            if len(raw) > MAX_DISCOVERY_FILE_BYTES or b"\x00" in raw:
                continue
            yield path, raw.decode("utf-8", errors="ignore")
        except (OSError, UnicodeError):
            continue


def _terms(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _hits(terms: list[str], text: str) -> dict[str, int]:
    return {term: len(re.findall(re.escape(term), text, flags=re.IGNORECASE)) for term in terms}


def _model_index(rows: list[dict[str, Any]]) -> list[tuple[str, str, list[str]]]:
    result: list[tuple[str, str, list[str]]] = []
    for row in rows:
        provider = str(row.get("provider") or "")
        canonical = str(row.get("canonical_id") or "")
        if not provider or not canonical or row.get("status") not in {"active", "preview"}:
            continue
        result.append((provider, canonical, [canonical, *_terms(row.get("aliases"))]))
    return result


def _custom_endpoint(text: str) -> str | None:
    """Return only a safe host/path hint for an unrecognised base URL."""
    pattern = r"(?i)(?:base[_-]?url|baseURL|endpoint|api[_-]?url)\s*[:=]\s*[\"']?(https?://[^\"'\\s)]+)"
    match = re.search(pattern, text)
    if not match:
        return None
    value = match.group(1).split("?")[0].rstrip("/,")
    return value[:160]


def _candidate_contract(candidate: dict[str, Any], *, identity_source: str, conflicts: list[str] | None = None) -> dict[str, Any]:
    evidence = dict(candidate.get("evidence") or {})
    return {
        "provider": candidate.get("provider"),
        "adapter": candidate.get("adapter"),
        "client_family": candidate.get("client_family") or ("openai-compatible" if "compatible" in str(candidate.get("adapter", "")) else "unknown"),
        "model": candidate.get("model"),
        "credential_name": candidate.get("credential_name"),
        "base_url": candidate.get("base_url"),
        "endpoint": candidate.get("endpoint"),
        "secret_source_required": "TARGET_REPOSITORY_GITHUB_SECRET" if candidate.get("credential_name") else "NONE",
        "confidence": candidate.get("confidence", "NONE"),
        "confidence_evidence": evidence,
        "identity_source": identity_source,
        "conflicts": list(conflicts or []),
        "client_sdk_candidates": candidate.get("client_sdk_candidates", []),
        "endpoint_candidates": candidate.get("endpoint_candidates", []),
        "model_candidates": candidate.get("model_candidates", []),
        "secret_name_candidates": candidate.get("secret_name_candidates", []),
    }


def discover(repo: Path, registry_root: Path) -> dict[str, Any]:
    providers = _rows(registry_root / "providers", "costdoctor.provider-registry.")
    models = _rows(registry_root / "models", "costdoctor.model-registry.")
    texts = list(_iter_text(repo))
    joined = "\n".join(text for _, text in texts)
    model_rows = _model_index(models)
    candidates: list[dict[str, Any]] = []
    for row in providers:
        detection = row.get("detection") or {}
        positive = _terms(detection.get("terms"))
        endpoints = _terms(detection.get("endpoint_terms"))
        sdk_terms = _terms(detection.get("sdk_terms"))
        secrets = _terms(row.get("secret_names"))
        term_hits = _hits(positive, joined)
        endpoint_hits = _hits(endpoints, joined)
        sdk_hits = _hits(sdk_terms, joined)
        secret_hits = _hits(secrets, joined)
        model_matches: list[tuple[int, str, str]] = []
        patterns = detection.get("model_patterns") or {}
        for model_id, pattern_terms in patterns.items():
            hit_count = sum(_hits(_terms(pattern_terms), joined).values())
            if hit_count:
                model_matches.append((hit_count, str(model_id), str(row.get("provider"))))
        for model_provider, canonical, aliases in model_rows:
            if model_provider != row.get("provider"):
                continue
            hit_count = sum(_hits(aliases, joined).values())
            if hit_count:
                model_matches.append((hit_count, canonical, model_provider))
        model_matches.sort(key=lambda item: (-item[0], item[1]))
        seen_models: set[str] = set()
        model_candidates: list[tuple[int, str, str]] = []
        for item in model_matches:
            if item[1] not in seen_models:
                seen_models.add(item[1])
                model_candidates.append(item)
        explicit_endpoint = sum(endpoint_hits.values()) > 0
        explicit_model = bool(model_candidates)
        credential = sum(secret_hits.values()) > 0
        sdk = sum(sdk_hits.values()) > 0
        generic = sum(term_hits.values()) > 0
        if not (explicit_endpoint or explicit_model or credential or sdk or generic):
            continue
        strong_hits = sum(endpoint_hits.values()) + sum(item[0] for item in model_candidates)
        medium_hits = sum(secret_hits.values())
        weak_hits = sum(sdk_hits.values()) + sum(term_hits.values())
        if explicit_endpoint or explicit_model:
            confidence = "STRONG"
        elif credential:
            confidence = "MEDIUM"
        elif sdk or generic:
            confidence = "WEAK"
        else:
            confidence = "NONE"
        endpoint = row.get("default_base_url") if explicit_endpoint else None
        candidates.append({
            "provider": str(row.get("provider")),
            "adapter": str(row.get("adapter")),
            "client_family": row.get("client_family") or row.get("compatible_client_family"),
            "score": strong_hits * 10 + medium_hits * 3 + weak_hits,
            "confidence": confidence,
            "model": model_candidates[0][1] if model_candidates else None,
            "credential_name": next((term for term, count in secret_hits.items() if count), None),
            "base_url": endpoint,
            "endpoint": endpoint,
            "client_sdk_candidates": sorted(term for term, count in sdk_hits.items() if count),
            "endpoint_candidates": sorted(term for term, count in endpoint_hits.items() if count),
            "model_candidates": [item[1] for item in model_candidates],
            "secret_name_candidates": sorted(term for term, count in secret_hits.items() if count),
            "evidence": {
                "strong_hits": strong_hits,
                "medium_hits": medium_hits,
                "weak_hits": weak_hits,
                "endpoint_hits": sum(endpoint_hits.values()),
                "secret_name_hits": sum(secret_hits.values()),
                "model_alias_hits": sum(item[0] for item in model_candidates),
                "sdk_hits": sum(sdk_hits.values()),
                "generic_term_hits": sum(term_hits.values()),
                "explicit_endpoint": explicit_endpoint,
                "explicit_model": explicit_model,
                "explicit_credential": credential,
            },
            "capabilities": row.get("capabilities") or {},
        })

    by_provider = {str(item["provider"]): item for item in candidates}
    endpoint_providers = {str(item["provider"]) for item in candidates if item["evidence"]["explicit_endpoint"]}
    model_providers = {str(item["provider"]) for item in candidates if item["evidence"]["explicit_model"]}
    credential_providers = {str(item["provider"]) for item in candidates if item["evidence"]["explicit_credential"]}
    sdk_providers = {str(item["provider"]) for item in candidates if item["client_sdk_candidates"]}
    all_explicit_providers = endpoint_providers | model_providers | credential_providers
    provider_groups = []
    for name in sorted(all_explicit_providers):
        item = by_provider[name]
        provider_groups.append(_candidate_contract(item, identity_source=("endpoint" if name in endpoint_providers else "model" if name in model_providers else "credential")))

    conflicts: list[str] = []
    selection_reason = "none"
    selected: dict[str, Any] | None = None
    status = "UNKNOWN_PROVIDER"
    custom_endpoint = _custom_endpoint(joined)
    if len(endpoint_providers) > 1:
        status = "MULTIPLE_PROVIDERS"
    elif len(endpoint_providers) == 1:
        endpoint_provider = next(iter(endpoint_providers))
        if model_providers - {endpoint_provider}:
            conflicts.append("MODEL_PROVIDER_ENDPOINT_MISMATCH")
        if credential_providers - {endpoint_provider}:
            conflicts.append("CREDENTIAL_PROVIDER_ENDPOINT_MISMATCH")
        if conflicts:
            status = "AMBIGUOUS_PROVIDER"
        else:
            selected = by_provider[endpoint_provider]
            selection_reason = "explicit_endpoint"
            status = "DETECTED"
    elif len(model_providers) > 1 or len(credential_providers) > 1:
        status = "MULTIPLE_PROVIDERS"
    elif len(model_providers) == 1:
        model_provider = next(iter(model_providers))
        if credential_providers - {model_provider}:
            conflicts.append("CREDENTIAL_PROVIDER_MODEL_MISMATCH")
            status = "AMBIGUOUS_PROVIDER"
        else:
            selected = by_provider[model_provider]
            selection_reason = "explicit_model"
            status = "DETECTED"
    elif len(credential_providers) == 1:
        selected = by_provider[next(iter(credential_providers))]
        selection_reason = "provider_credential"
        status = "DETECTED"
    elif len(sdk_providers) == 1:
        selected = by_provider[next(iter(sdk_providers))]
        selection_reason = "sdk_transport_only"
        status = "DETECTED"
    elif custom_endpoint and sdk_providers:
        # Custom transport is intentionally not direct OpenAI and remains
        # unpriced until a registry provider/model contract exists.
        selected = {
            "provider": "OPENAI_COMPATIBLE_CUSTOM",
            "adapter": "openai_compatible_v1",
            "client_family": "openai-compatible",
            "model": None,
            "credential_name": None,
            "base_url": custom_endpoint,
            "endpoint": custom_endpoint,
            "confidence": "MEDIUM",
            "evidence": {"custom_endpoint": True, "sdk_transport": True},
            "client_sdk_candidates": sorted(sdk_providers),
            "endpoint_candidates": [custom_endpoint],
            "model_candidates": [],
            "secret_name_candidates": [],
        }
        selection_reason = "custom_endpoint"
        status = "OPENAI_COMPATIBLE_CUSTOM"
    if selected is None and status == "MULTIPLE_PROVIDERS":
        selected = {
            "provider": "MULTIPLE_PROVIDERS",
            "adapter": "provider_group_v1",
            "client_family": "multiple",
            "model": None,
            "credential_name": None,
            "base_url": None,
            "endpoint": None,
            "confidence": "NONE",
            "evidence": {"provider_group_count": len(provider_groups)},
            "conflicts": ["MULTIPLE_EXPLICIT_PROVIDERS"],
            "client_sdk_candidates": sorted(sdk_providers),
            "endpoint_candidates": [],
            "model_candidates": [],
            "secret_name_candidates": [],
        }
    if selected is None and status == "AMBIGUOUS_PROVIDER":
        selected = {
            "provider": "AMBIGUOUS_PROVIDER",
            "adapter": "provider_contract_v1",
            "client_family": "ambiguous",
            "model": None,
            "credential_name": None,
            "base_url": None,
            "endpoint": None,
            "confidence": "NONE",
            "evidence": {"conflicts": conflicts},
            "conflicts": conflicts,
            "client_sdk_candidates": sorted(sdk_providers),
            "endpoint_candidates": [],
            "model_candidates": [],
            "secret_name_candidates": [],
        }
    if selected is None:
        selected = {
            "provider": None,
            "adapter": "generic_v1",
            "client_family": "unknown",
            "model": None,
            "credential_name": None,
            "base_url": None,
            "endpoint": None,
            "confidence": "NONE",
            "evidence": {"generic_terms_only": True},
            "client_sdk_candidates": [],
            "endpoint_candidates": [],
            "model_candidates": [],
            "secret_name_candidates": [],
        }
    selected_contract = _candidate_contract(selected, identity_source=selection_reason or "none", conflicts=conflicts or selected.get("conflicts"))
    selected_contract["transport_provider_candidates"] = sorted(sdk_providers)
    selected_contract["provider_identity_status"] = status
    candidates.sort(key=lambda item: (-_CONFIDENCE_RANK.get(str(item.get("confidence")), 0), -int(item.get("score", 0)), str(item.get("provider"))))
    return {
        "status": status,
        "selection_reason": selection_reason,
        "provider_candidates": [
            {key: item[key] for key in ("provider", "adapter", "client_family", "score", "confidence", "evidence", "model", "credential_name", "base_url", "endpoint", "client_sdk_candidates", "endpoint_candidates", "model_candidates", "secret_name_candidates")}
            for item in candidates
        ],
        "provider_groups": provider_groups,
        "selected": selected_contract,
        "conflicts": conflicts,
        "transport_provider_candidates": sorted(sdk_providers),
        "custom_endpoint_hint": custom_endpoint,
        "registry_rows_considered": len(providers),
        "model_rows_considered": len(models),
        "text_units_scanned": len(texts),
    }


def stage2_level(discovery: dict[str, Any], *, workload_ready: bool, deterministic_measurement: bool = False, priced: bool = False, provider_usage: bool = False) -> str:
    if provider_usage:
        return "L5_VERIFIED_SAVINGS"
    if priced and deterministic_measurement and discovery.get("status") == "DETECTED":
        return "L3_ESTIMATED_COST_SAVINGS"
    if deterministic_measurement:
        return "L2_DETERMINISTIC_MEASUREMENT"
    return "L1_STRUCTURAL_DIAGNOSIS"
