#!/usr/bin/env python3
"""Runner-local, sanitized target repository binding and precheck.

The target checkout is read only and never copied to the engine repository or
written to an artifact.  Only aggregate counts, provider hints and hashes are
emitted.  A workload is usable for an actual run only when the target itself
provides a bounded, sanitized `.costdoctor/target-workload.json` descriptor.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from costdoctor.provider_discovery import EXCLUDED, TEXT_SUFFIXES, discover  # noqa: E402


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def git_value(repo: Path, *args: str) -> str:
    try:
        # The runner may materialize a checkout under a different OS account
        # (for example, a local evidence replay).  Scope the safe-directory
        # exception to this exact read-only target path so commit readback is
        # never silently replaced with UNKNOWN.
        return subprocess.check_output(["git", "-c", f"safe.directory={repo}", "-C", str(repo), *args], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


MAX_MEASUREMENT_FILES = 1200
MAX_MEASUREMENT_FILE_BYTES = 500_000
MAX_MEASUREMENT_TOTAL_BYTES = 5_000_000
MAX_MEASUREMENT_LINE_CHARS = 8192
SENSITIVE_NAME = re.compile(r"(?i)^(?:\.env(?:\..*)?|credentials?|secrets?|tokens?|private.?key|.*\.(?:pem|key))$")


def iter_files(repo: Path):
    """Yield a stable, bounded file list without reading file bodies first."""
    paths: list[Path] = []
    try:
        candidates = sorted(repo.rglob("*"), key=lambda item: str(item.relative_to(repo)).lower())
    except OSError:
        candidates = []
    for path in candidates:
        try:
            relative = path.relative_to(repo)
            if path.is_symlink() or not path.is_file() or any(part in EXCLUDED for part in relative.parts) or SENSITIVE_NAME.search(path.name):
                continue
        except OSError:
            continue
        paths.append(path)
        if len(paths) >= MAX_MEASUREMENT_FILES:
            break
    yield from paths


def _read_bounded_text(path: Path) -> tuple[str | None, str | None, int]:
    """Read only up to the per-file budget; never read then slice."""
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_MEASUREMENT_FILE_BYTES + 1)
        if len(raw) > MAX_MEASUREMENT_FILE_BYTES:
            return None, "FILE_SIZE_LIMIT", len(raw)
        if b"\x00" in raw:
            return None, "BINARY_FILE", len(raw)
        return raw.decode("utf-8", errors="ignore"), None, len(raw)
    except (OSError, UnicodeError):
        return None, "READ_ERROR", 0


def source_category(path: Path, repo: Path) -> str:
    """Return an aggregate-only source class; never expose the path."""
    rel = path.relative_to(repo)
    parts = [part.lower() for part in rel.parts]
    name = parts[-1] if parts else ""
    if any(part in {"vendor", "node_modules", "dist", "build", "generated"} for part in parts):
        return "GENERATED_VENDOR"
    if any(part in {"test", "tests", "eval", "evals", "fixture", "fixtures"} for part in parts) or re.search(r"(^|[._-])(test|spec|fixture|eval)([._-]|$)", name):
        return "TEST_EVAL"
    if any(part in {"docs", "examples", "example", "samples"} for part in parts) or Path(name).suffix.lower() in {".md", ".mdx", ".rst"}:
        return "DOCS_EXAMPLE"
    if Path(name).suffix.lower() in {".json", ".yml", ".yaml", ".toml"} or re.search(r"(config|settings|prompt|policy)", name, re.I):
        return "CONFIG"
    return "RUNTIME_CODE"


def workload_descriptor(repo: Path) -> dict[str, Any]:
    candidates = [repo / ".costdoctor" / "target-workload.json", repo / ".costdoctor" / "verified-workload.json"]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {"ready": False, "reason": "TARGET_WORKLOAD_DESCRIPTOR_INVALID", "fingerprint": None, "item_count": 0}
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list) or not payload["items"]:
            return {"ready": False, "reason": "TARGET_WORKLOAD_DESCRIPTOR_INVALID", "fingerprint": None, "item_count": 0}
        safe = {"kind": str(payload.get("kind", "target")), "item_count": len(payload["items"]), "quality": payload.get("quality", "exact")}
        digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        return {"ready": True, "kind": safe["kind"], "item_count": safe["item_count"], "quality": str(safe["quality"]), "fingerprint": digest, "source_present": True}
    # No project-specific workload detector is used.  Generic fixture files
    # are reported as candidates only; actual execution requires a bounded
    # descriptor owned by the target repository.
    fixture_candidates = [path for path in iter_files(repo) if path.suffix.lower() in {".jsonl", ".json", ".yaml", ".yml"} and any(part in {"evals", "fixtures", "tests"} for part in path.relative_to(repo).parts)]
    if fixture_candidates:
        marker_body = {"candidate_count": len(fixture_candidates), "kind": "repository-derived-fixture-candidate"}
        digest = hashlib.sha256(json.dumps(marker_body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        return {"ready": False, "kind": marker_body["kind"], "item_count": len(fixture_candidates), "quality": "descriptor_required_for_actual", "fingerprint": digest, "source_present": True, "candidate_count": len(fixture_candidates)}
    return {"ready": False, "reason": "TARGET_WORKLOAD_DESCRIPTOR_REQUIRED", "fingerprint": None, "item_count": 0, "source_present": False}


def _canonical_counts(static_report: dict[str, Any] | None) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in (static_report or {}).get("findings", []):
        rule = str(item.get("rule", "")).upper()
        if not rule:
            continue
        result[rule] = int(item.get("signal_count", 0) or 0)
    return result


def _legacy_bounded_deterministic_measurement(repo: Path) -> dict[str, Any]:
    """Collect reproducible, offline-only aggregate measurements.

    This reads bounded text slices and never imports, installs, or executes
    target code.  Values describe source structure, not provider usage or a
    billed savings rate.
    """
    total_chars = 0
    context_chars = 0
    repeated_context_chars = 0
    global_repeated_source_chars = 0
    repeated_lines = 0
    retry_bounds: list[int] = []
    retry_values: list[int] = []
    retry_disabled = 0
    retry_active = 0
    retry_unknown = 0
    cache_candidate_chars = 0
    cache_relevant_occurrences = 0
    cache_ordinary_occurrences = 0
    budget_values: list[int] = []
    seen: dict[str, int] = {}
    context_seen: dict[str, int] = {}
    units = 0
    category_counts = {key: 0 for key in ("RUNTIME_CODE", "CONFIG", "TEST_EVAL", "DOCS_EXAMPLE", "GENERATED_VENDOR", "UNKNOWN")}
    overlap = {"MODEL_CALL+RETRY_LOOP": 0, "MODEL_CALL+CACHE_SIGNAL": 0, "MODEL_CALL+TOKEN_LIMIT": 0}
    total_bytes = 0
    for path in iter_files(repo):
        if units >= 1200 or total_bytes >= 5_000_000:
            break
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")[:500_000]
        except OSError:
            continue
        units += 1
        total_bytes += len(text.encode("utf-8", errors="ignore"))
        category = source_category(path, repo)
        category_counts[category] += 1
        total_chars += len(text)
        lines = [line.strip()[:8192] for line in text.splitlines() if len(line.strip()) >= 40]
        local_counts: dict[str, int] = {}
        for line in lines[:10_000]:
            normalized = re.sub(r"\s+", " ", line)
            local_counts[normalized] = local_counts.get(normalized, 0) + 1
            lower = normalized.lower()
            is_context_line = any(mark in lower for mark in ("prompt", "context", "system", "instruction", "messages", "payload"))
            if is_context_line:
                context_chars += len(normalized)
                context_seen[normalized] = context_seen.get(normalized, 0) + 1
            if any(mark in lower for mark in ("cache", "cached", "cache_control")):
                if re.search(r"\b(prompt|input|token|model|llm|embedding|cache_control|system|context)\b", lower):
                    cache_candidate_chars += len(normalized)
                    cache_relevant_occurrences += len(re.findall(r"\b(?:cache|cached|lru_cache|cache_control)\b", lower))
                elif re.search(r"\b(dependency|package|filesystem|file|ci|build|artifact|npm|pip)\b", lower):
                    cache_ordinary_occurrences += len(re.findall(r"\b(?:cache|cached|lru_cache|cache_control)\b", lower))
        for normalized, count in local_counts.items():
            seen[normalized] = seen.get(normalized, 0) + count
        for match in re.finditer(r"(?i)\b(?:max_retries|maxRetries|num_retries|retries|retry_count|attempts|stop_after_attempt)\s*[:=]\s*(\d{1,3})", text):
            value = min(100, int(match.group(1)))
            retry_values.append(value)
            if category in {"DOCS_EXAMPLE", "TEST_EVAL"}:
                retry_unknown += 1
            elif value == 0:
                retry_disabled += 1
            else:
                retry_active += 1
                retry_bounds.append(value + 1)
        for match in re.finditer(r"(?i)\b(?:max_tokens|max_output_tokens|num_predict|num_ctx|context_window)\s*[:=]\s*(\d{1,7})", text):
            budget_values.append(int(match.group(1)))
        for line in lines[:10_000]:
            lower = line.lower()
            hits = {
                "MODEL_CALL": bool(re.search(r"\b(?:invoke|generate|chat\.completions(?:\.create)?|responses\.create|messages\.create|generatecontent|completion)\s*\(", lower)),
                "RETRY_LOOP": bool(re.search(r"\b(?:retry|retries|max_retries|maxretries|backoff|tenacity)\b", lower)),
                "CACHE_SIGNAL": bool(re.search(r"\b(?:cache|cached|lru_cache|cache_control)\b", lower) and re.search(r"\b(prompt|input|token|model|llm|embedding|cache_control|system|context)\b", lower)),
                "TOKEN_LIMIT": bool(re.search(r"\b(?:max_tokens|max_output_tokens|num_predict|num_ctx|context_window)\b", lower)),
            }
            for left, right in (("MODEL_CALL", "RETRY_LOOP"), ("MODEL_CALL", "CACHE_SIGNAL"), ("MODEL_CALL", "TOKEN_LIMIT")):
                if hits[left] and hits[right]:
                    overlap[f"{left}+{right}"] += 1
    # Keep the measurement universe explicit.  Repeated lines from the whole
    # repository are useful as a separate structural signal, but they must not
    # inflate the repeated *context* denominator used for Before/After/Delta.
    global_repeated_source_chars = sum(len(key) * (count - 1) for key, count in seen.items() if count > 1)
    repeated_context_chars = sum(len(key) * (count - 1) for key, count in context_seen.items() if count > 1)
    repeated_lines = sum(count - 1 for count in context_seen.values() if count > 1)
    denominator = max(1, context_chars)
    repetition_ratio = round(min(1.0, repeated_context_chars / denominator), 6) if context_chars else 0.0
    before_tokens = math.ceil(context_chars / 4) if context_chars else 0
    delta_tokens = math.ceil(repeated_context_chars / 4) if repeated_context_chars else 0
    optimized_tokens = max(0, before_tokens - delta_tokens)
    delta_invariant = bool(
        0 <= delta_tokens <= before_tokens
        and optimized_tokens >= 0
        and before_tokens - optimized_tokens == delta_tokens
    )
    if not delta_invariant:
        # Never publish mathematically inconsistent quantities.  Structural
        # character counts remain available, while token Before/After/Delta
        # are explicitly unavailable to all user-facing/reporting layers.
        before_tokens = None
        delta_tokens = None
        optimized_tokens = None
    available = bool(repeated_context_chars or retry_active or retry_disabled or cache_candidate_chars or budget_values)
    negative = "RETRY_DISABLED_OBSERVED" if retry_disabled and not retry_active else "RETRY_ACTIVE_CONFIGURED" if retry_active else "RETRY_CONFIG_UNKNOWN" if retry_bounds or retry_unknown else "NONE"
    return {
        "schema": "costdoctor.deterministic-measurement.v1",
        "available": available,
        "measurement_grade": "L2_DETERMINISTIC_MEASUREMENT" if available else "L1_STRUCTURAL_DIAGNOSIS",
        "execution": {"target_code_executed": False, "provider_calls": 0, "secret_used": False},
        "scope": {"text_units": units, "bounded_chars_per_unit": 500000, "aggregate_only": True, "bounded_total_chars": 5000000, "analyzed_bytes": total_bytes, "skipped_due_to_size": 0, "excluded_generated": category_counts.get("GENERATED_VENDOR", 0)},
        "source_categories": category_counts,
        "context": {"candidate_chars": context_chars, "candidate_token_estimate": before_tokens, "before_token_estimate": before_tokens, "optimized_token_estimate": optimized_tokens, "avoidable_delta_tokens": delta_tokens, "repeated_candidate_chars": repeated_context_chars, "repeated_token_estimate": delta_tokens, "repeated_candidate_ratio": repetition_ratio, "repeated_line_candidates": repeated_lines, "global_repeated_source_chars": global_repeated_source_chars, "measurement_universe": "CONTEXT_CANDIDATE_LINES_ONLY", "delta_invariant": {"status": "PASS" if delta_invariant else "FAIL", "rule": "0 <= delta <= before; optimized >= 0; before - optimized == delta"}, "token_estimate_method": "UTF-8 source characters / 4; approximate, not provider usage"},
        "retry": {"configured_upper_bound_attempts": max(retry_bounds) if retry_bounds else None, "observed_config_count": len(retry_bounds), "configured_values": sorted(set(retry_values))[:20], "active_config_count": retry_active, "disabled_config_count": retry_disabled, "unknown_config_count": retry_unknown, "negative_evidence": negative},
        "cache": {"cacheable_candidate_chars": cache_candidate_chars, "llm_relevant_occurrences": cache_relevant_occurrences, "ordinary_cache_occurrences": cache_ordinary_occurrences, "repeated_payload_candidate": bool(cache_candidate_chars and repeated_context_chars)},
        "budget": {"declared_values": sorted(set(budget_values))[:20], "count": len(budget_values)},
        "overlap": overlap,
        "claim_boundary": "structural source measurement; not provider usage and not billed cost savings",
    }


def _bounded_deterministic_measurement(repo: Path) -> dict[str, Any]:
    """Offline request-path measurement with explicit bounded coverage.

    The public path never executes target code or calls a model.  It reports
    safe relative locations and separates runtime calls from test/docs signals.
    """
    context_chars = 0
    repeated_context_chars = 0
    global_repeated_source_chars = 0
    repeated_lines = 0
    retry_bounds: list[int] = []
    retry_values: list[int] = []
    retry_disabled = 0
    retry_active = 0
    retry_unknown = 0
    cache_candidate_chars = 0
    cache_relevant_occurrences = 0
    cache_ordinary_occurrences = 0
    budget_values: list[int] = []
    seen: dict[str, int] = {}
    context_seen: dict[str, int] = {}
    units = 0
    skipped_due_to_size = 0
    skipped_binary = 0
    read_errors = 0
    total_bytes = 0
    category_counts = {key: 0 for key in ("RUNTIME_CODE", "CONFIG", "TEST_EVAL", "DOCS_EXAMPLE", "GENERATED_VENDOR", "UNKNOWN")}
    overlap = {"MODEL_CALL+RETRY_LOOP": 0, "MODEL_CALL+CACHE_SIGNAL": 0, "MODEL_CALL+TOKEN_LIMIT": 0}
    call_path_evidence: list[dict[str, Any]] = []
    retry_evidence: list[dict[str, Any]] = []
    llm_cache_evidence: list[dict[str, Any]] = []
    ordinary_cache_evidence: list[dict[str, Any]] = []
    invocation_pattern = re.compile(r"(?i)\b(?:invoke|generate|chat\.completions(?:\.create)?|responses\.create|messages\.create|generatecontent|completion|embed|embeddings)\s*\(")
    sdk_import_pattern = re.compile(r"(?i)^\s*(?:from|import)\s+.*\b(?:openai|anthropic|gemini|langchain|ollama|upstage|azure|bedrock|ChatOpenAI|OpenAI)\b")
    retry_pattern = re.compile(r"(?i)\b(max_retries|maxRetries|num_retries|retries|retry_count|attempts|stop_after_attempt)\s*[:=(]\s*(\d{1,3})")
    budget_pattern = re.compile(r"(?i)\b(max_tokens|max_output_tokens|num_predict|num_ctx|context_window)\s*[:=]\s*(\d{1,7})")
    for path in iter_files(repo):
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        relative = str(path.relative_to(repo)).replace("\\", "/")
        text, read_status, raw_size = _read_bounded_text(path)
        if read_status == "FILE_SIZE_LIMIT":
            skipped_due_to_size += 1
            continue
        if read_status == "BINARY_FILE":
            skipped_binary += 1
            continue
        if read_status == "READ_ERROR" or text is None:
            read_errors += 1
            continue
        if total_bytes + raw_size > MAX_MEASUREMENT_TOTAL_BYTES:
            skipped_due_to_size += 1
            continue
        units += 1
        total_bytes += raw_size
        category = source_category(path, repo)
        category_counts[category] += 1
        all_lines = text.splitlines()[:10_000]
        local_counts: dict[str, int] = {}
        for line_number, raw_line in enumerate(all_lines, 1):
            normalized = re.sub(r"\s+", " ", raw_line.strip())[:MAX_MEASUREMENT_LINE_CHARS]
            if not normalized:
                continue
            local_counts[normalized] = local_counts.get(normalized, 0) + 1
            lower = normalized.lower()
            is_context_line = any(mark in lower for mark in ("prompt", "context", "system", "instruction", "messages", "payload"))
            if is_context_line:
                context_chars += len(normalized)
                context_seen[normalized] = context_seen.get(normalized, 0) + 1
            cache_hits = len(re.findall(r"\b(?:cache|cached|lru_cache|cache_control)\b", lower))
            if cache_hits:
                llm_context = bool(re.search(r"\b(prompt|input|token|model|llm|embedding|cache_control|system|context)\b", lower))
                ordinary_context = bool(re.search(r"\b(dependency|package|filesystem|file|ci|build|artifact|npm|pip)\b", lower))
                if llm_context:
                    cache_candidate_chars += len(normalized)
                    cache_relevant_occurrences += cache_hits
                    if len(llm_cache_evidence) < 50:
                        llm_cache_evidence.append({"relative_path": relative, "line_start": line_number, "line_end": line_number, "source_category": category, "condition": "AI-input/cache terms co-occur; prefix stability, TTL and hit rate unverified"})
                elif ordinary_context:
                    cache_ordinary_occurrences += cache_hits
                    if len(ordinary_cache_evidence) < 50:
                        ordinary_cache_evidence.append({"relative_path": relative, "line_start": line_number, "line_end": line_number, "source_category": category})
            call_matches = list(invocation_pattern.finditer(raw_line))
            for call_match in call_matches:
                runtime_relevant = category in {"RUNTIME_CODE", "CONFIG"}
                call_kind = "runtime_invocation" if runtime_relevant else "test_eval_invocation" if category == "TEST_EVAL" else "docs_example_invocation" if category == "DOCS_EXAMPLE" else "non_runtime_invocation"
                if len(call_path_evidence) < 100:
                    call_path_evidence.append({"relative_path": relative, "line_start": line_number, "line_end": line_number, "call": call_match.group(0).strip().rstrip("("), "call_kind": call_kind, "runtime_relevance": "RUNTIME" if runtime_relevant else "NON_PRODUCTION", "source_category": category, "confidence": "STRONG" if runtime_relevant else "WEAK"})
            if sdk_import_pattern.search(raw_line) and len(call_path_evidence) < 100:
                call_path_evidence.append({"relative_path": relative, "line_start": line_number, "line_end": line_number, "call": "SDK_IMPORT", "call_kind": "sdk_import_only", "runtime_relevance": "UNRESOLVED", "source_category": category, "confidence": "MEDIUM" if category in {"RUNTIME_CODE", "CONFIG"} else "WEAK"})
            hits = {
                "MODEL_CALL": bool(call_matches),
                "RETRY_LOOP": bool(re.search(r"\b(?:retry|retries|max_retries|maxretries|backoff|tenacity)\b", lower)),
                "CACHE_SIGNAL": bool(cache_hits and re.search(r"\b(prompt|input|token|model|llm|embedding|cache_control|system|context)\b", lower)),
                "TOKEN_LIMIT": bool(re.search(r"\b(?:max_tokens|max_output_tokens|num_predict|num_ctx|context_window)\b", lower)),
            }
            for left, right in (("MODEL_CALL", "RETRY_LOOP"), ("MODEL_CALL", "CACHE_SIGNAL"), ("MODEL_CALL", "TOKEN_LIMIT")):
                if hits[left] and hits[right]:
                    overlap[f"{left}+{right}"] += 1
        for normalized, count in local_counts.items():
            seen[normalized] = seen.get(normalized, 0) + count
        for match in retry_pattern.finditer(text):
            key = match.group(1)
            value = min(100, int(match.group(2)))
            retry_values.append(value)
            line_number = text.count("\n", 0, match.start()) + 1
            runtime_relevant = category in {"RUNTIME_CODE", "CONFIG"}
            if category in {"DOCS_EXAMPLE", "TEST_EVAL"}:
                retry_unknown += 1
            elif value == 0:
                retry_disabled += 1
            else:
                retry_active += 1
                if key == "stop_after_attempt":
                    retry_bounds.append(value)
            if len(retry_evidence) < 100:
                retry_evidence.append({"relative_path": relative, "line_start": line_number, "line_end": line_number, "setting": key, "configured_value": value, "source_category": category, "active_runtime_candidate": runtime_relevant and value > 0, "semantics": "total_attempts" if key == "stop_after_attempt" else "additional_retries_or_library_specific; total attempts not assumed", "attempts_upper_bound": value if key == "stop_after_attempt" and runtime_relevant and value > 0 else None})
        for match in budget_pattern.finditer(text):
            budget_values.append(int(match.group(2)))
    global_repeated_source_chars = sum(len(key) * (count - 1) for key, count in seen.items() if count > 1)
    repeated_context_chars = sum(len(key) * (count - 1) for key, count in context_seen.items() if count > 1)
    repeated_lines = sum(count - 1 for count in context_seen.values() if count > 1)
    repetition_ratio = round(min(1.0, repeated_context_chars / context_chars), 6) if context_chars else 0.0
    before_tokens = math.ceil(context_chars / 4) if context_chars else 0
    delta_tokens = math.ceil(repeated_context_chars / 4) if repeated_context_chars else 0
    optimized_tokens = max(0, before_tokens - delta_tokens)
    delta_invariant = bool(0 <= delta_tokens <= before_tokens and optimized_tokens >= 0 and before_tokens - optimized_tokens == delta_tokens)
    if not delta_invariant:
        before_tokens = optimized_tokens = delta_tokens = None
    runtime_invocations = sum(1 for item in call_path_evidence if item.get("call_kind") == "runtime_invocation")
    test_eval_invocations = sum(1 for item in call_path_evidence if item.get("call_kind") == "test_eval_invocation")
    docs_invocations = sum(1 for item in call_path_evidence if item.get("call_kind") == "docs_example_invocation")
    sdk_imports = sum(1 for item in call_path_evidence if item.get("call_kind") == "sdk_import_only")
    available = bool(repeated_context_chars or retry_active or retry_disabled or cache_candidate_chars or budget_values or call_path_evidence)
    negative = "RETRY_DISABLED_OBSERVED" if retry_disabled and not retry_active else "RETRY_ACTIVE_CONFIGURED" if retry_active else "RETRY_CONFIG_UNKNOWN" if retry_unknown else "NONE"
    return {
        "schema": "costdoctor.deterministic-measurement.v2",
        "available": available,
        "measurement_grade": "L2_DETERMINISTIC_MEASUREMENT" if available else "L1_STRUCTURAL_DIAGNOSIS",
        "execution": {"target_code_executed": False, "provider_calls": 0, "secret_used": False},
        "scope": {"text_units": units, "bounded_chars_per_unit": MAX_MEASUREMENT_FILE_BYTES, "aggregate_only": False, "bounded_total_chars": MAX_MEASUREMENT_TOTAL_BYTES, "analyzed_bytes": total_bytes, "skipped_due_to_size": skipped_due_to_size, "skipped_binary": skipped_binary, "read_errors": read_errors, "excluded_generated": category_counts.get("GENERATED_VENDOR", 0), "max_files": MAX_MEASUREMENT_FILES, "coverage_status": "partial_bounded" if skipped_due_to_size or read_errors else "complete_within_bounds"},
        "source_categories": category_counts,
        "context": {"candidate_chars": context_chars, "candidate_token_estimate": before_tokens, "before_token_estimate": before_tokens, "optimized_token_estimate": optimized_tokens, "avoidable_delta_tokens": delta_tokens, "repeated_candidate_chars": repeated_context_chars, "repeated_token_estimate": delta_tokens, "repeated_candidate_ratio": repetition_ratio, "repeated_line_candidates": repeated_lines, "global_repeated_source_chars": global_repeated_source_chars, "measurement_universe": "CONTEXT_CANDIDATE_LINES_ONLY", "delta_invariant": {"status": "PASS" if delta_invariant else "FAIL", "rule": "0 <= delta <= before; optimized >= 0; before - optimized == delta"}, "token_estimate_method": "UTF-8 source characters / 4; approximate, not provider usage"},
        "runtime": {"runtime_invocation_count": runtime_invocations, "test_eval_invocation_count": test_eval_invocations, "docs_example_invocation_count": docs_invocations, "sdk_import_only_count": sdk_imports, "call_path_evidence": call_path_evidence, "production_cost_candidate": runtime_invocations > 0},
        "request_paths": call_path_evidence,
        "retry": {"configured_upper_bound_attempts": max(retry_bounds) if retry_bounds else None, "observed_config_count": len(retry_evidence), "configured_values": sorted(set(retry_values))[:20], "active_config_count": retry_active, "disabled_config_count": retry_disabled, "unknown_config_count": retry_unknown, "negative_evidence": negative, "semantics": "library-specific; stop_after_attempt is total attempts, generic max_retries total attempts unknown", "evidence": retry_evidence},
        "cache": {"cacheable_candidate_chars": cache_candidate_chars, "llm_relevant_occurrences": cache_relevant_occurrences, "ordinary_cache_occurrences": cache_ordinary_occurrences, "repeated_payload_candidate": bool(cache_candidate_chars and repeated_context_chars), "llm_cache_evidence": llm_cache_evidence, "ordinary_cache_evidence": ordinary_cache_evidence, "prefix_stability": "UNVERIFIED", "hit_rate": "UNKNOWN", "billing_effect": "UNKNOWN"},
        "budget": {"declared_values": sorted(set(budget_values))[:20], "count": len(budget_values)},
        "overlap": overlap,
        "claim_boundary": "structural source measurement; not provider usage and not billed cost savings",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--target-repository", required=True)
    parser.add_argument("--target-ref", default="main")
    parser.add_argument("--static-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repository.resolve()
    if not repo.is_dir() or not (repo / ".git").exists():
        write_json(args.output, {"schema": "costdoctor.target-binding.v1", "status": "BLOCKED", "reason": "TARGET_CHECKOUT_REQUIRED", "raw_source_stored": False})
        return 2
    counts = {"files": 0, "retry_signals": 0, "cache_signals": 0, "model_call_signals": 0}
    registry_root = Path(__file__).resolve().parents[1] / "registry"
    detection = discover(repo, registry_root)
    for path in iter_files(repo):
        counts["files"] += 1
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text, read_status, _ = _read_bounded_text(path)
        if text is None or read_status in {"FILE_SIZE_LIMIT", "BINARY_FILE", "READ_ERROR"}:
            continue
        counts["retry_signals"] += len(re.findall(r"(?i)\bretr(?:y|ies|ied)\b", text))
        counts["cache_signals"] += len(re.findall(r"(?i)\bcach(?:e|ed|ing)\b", text))
        counts["model_call_signals"] += len(re.findall(r"(?i)(?:openai|anthropic|gemini|azure|bedrock|upstage|ollama|llm|chat\.completions|responses\.create|generateContent)", text))
    commit = git_value(repo, "rev-parse", "HEAD")
    workload = workload_descriptor(repo)
    binding_body = {"repository": args.target_repository, "ref": args.target_ref, "commit": commit, "counts": counts, "provider_detection": detection, "workload": workload}
    fingerprint = hashlib.sha256(json.dumps(binding_body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    static = None
    static_payload = None
    if args.static_report and args.static_report.is_file():
        try:
            static_payload = json.loads(args.static_report.read_text(encoding="utf-8"))
            static = {"status": static_payload.get("verdict", "UNKNOWN"), "finding_count": len(static_payload.get("findings", []))}
        except (OSError, UnicodeError, json.JSONDecodeError):
            static = {"status": "UNKNOWN", "finding_count": 0}
    canonical = _canonical_counts(static_payload)
    deterministic = _bounded_deterministic_measurement(repo)
    result = {
        "schema": "costdoctor.target-binding.v1",
        "status": "PASS",
        "tool_repository": os.environ.get("GITHUB_REPOSITORY", "UNKNOWN"),
        "tool_commit": git_value(Path(__file__).resolve().parents[2], "rev-parse", "HEAD"),
        "target_repository": args.target_repository,
        "target_ref": args.target_ref,
        "target_commit": commit,
        "target_fingerprint": fingerprint,
        "static_precheck": {"canonical_signal_counts": canonical or counts, "aggregate_counts": canonical or counts, "raw_scan_counts": counts, "action_report": static, "canonical_source": "TARGET_STATIC_PRECHECK", "not_billing_or_savings": True},
        "provider_contract": detection["selected"],
        "provider_detection": detection,
        "provider_resolution": {
            "status": detection.get("status"),
            "selection_reason": detection.get("selection_reason"),
            "selected_contract": detection.get("selected"),
            "provider_groups": detection.get("provider_groups", []),
            "conflicts": detection.get("conflicts", []),
            "client_vs_provider": {
                "transport_provider_candidates": detection.get("transport_provider_candidates", []),
                "resolved_provider": (detection.get("selected") or {}).get("provider"),
                "client_family": (detection.get("selected") or {}).get("client_family"),
            },
            "identity_precedence": ["explicit_endpoint", "explicit_model", "provider_credential", "sdk_transport", "generic_terms"],
        },
        "workload": workload,
        "deterministic_measurement": deterministic,
        "privacy": {"raw_source_stored": False, "raw_filenames_stored": False, "raw_prompt_stored": False, "raw_response_stored": False},
        "runner_scope": "runner-local-shadow-read-only",
    }
    write_json(args.output, result)
    print(json.dumps({"status": result["status"], "target_fingerprint": fingerprint, "workload_ready": result["workload"]["ready"], "files": counts["files"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
