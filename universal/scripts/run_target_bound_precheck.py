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
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


def iter_files(repo: Path):
    for path in repo.rglob("*"):
        if not path.is_file() or any(part in EXCLUDED for part in path.relative_to(repo).parts):
            continue
        yield path


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


def _bounded_deterministic_measurement(repo: Path) -> dict[str, Any]:
    """Collect reproducible, offline-only aggregate measurements.

    This reads bounded text slices and never imports, installs, or executes
    target code.  Values describe source structure, not provider usage or a
    billed savings rate.
    """
    total_chars = 0
    context_chars = 0
    repeated_context_chars = 0
    repeated_lines = 0
    retry_bounds: list[int] = []
    cache_candidate_chars = 0
    budget_values: list[int] = []
    seen: dict[str, int] = {}
    units = 0
    for path in iter_files(repo):
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")[:500_000]
        except OSError:
            continue
        units += 1
        total_chars += len(text)
        lines = [line.strip() for line in text.splitlines() if len(line.strip()) >= 40]
        local_counts: dict[str, int] = {}
        for line in lines[:10_000]:
            normalized = re.sub(r"\s+", " ", line)
            local_counts[normalized] = local_counts.get(normalized, 0) + 1
            lower = normalized.lower()
            if any(mark in lower for mark in ("prompt", "context", "system", "instruction", "messages", "payload")):
                context_chars += len(normalized)
            if any(mark in lower for mark in ("cache", "cached", "cache_control")):
                cache_candidate_chars += len(normalized)
        for normalized, count in local_counts.items():
            seen[normalized] = seen.get(normalized, 0) + count
            if count > 1:
                repeated_lines += count - 1
                repeated_context_chars += len(normalized) * (count - 1)
        for match in re.finditer(r"(?i)\b(?:max_retries|num_retries|retries)\s*[:=]\s*(\d{1,3})", text):
            retry_bounds.append(min(100, int(match.group(1)) + 1))
        for match in re.finditer(r"(?i)\b(?:max_tokens|max_output_tokens|num_predict|num_ctx|context_window)\s*[:=]\s*(\d{1,7})", text):
            budget_values.append(int(match.group(1)))
    global_repeated_chars = sum(len(key) * (count - 1) for key, count in seen.items() if count > 1)
    repeated_context_chars = max(repeated_context_chars, global_repeated_chars)
    denominator = max(1, context_chars)
    repetition_ratio = round(min(1.0, repeated_context_chars / denominator), 6) if context_chars else 0.0
    available = bool(repeated_context_chars or retry_bounds or cache_candidate_chars or budget_values)
    return {
        "schema": "costdoctor.deterministic-measurement.v1",
        "available": available,
        "measurement_grade": "L2_DETERMINISTIC_MEASUREMENT" if available else "L1_STRUCTURAL_DIAGNOSIS",
        "execution": {"target_code_executed": False, "provider_calls": 0, "secret_used": False},
        "scope": {"text_units": units, "bounded_chars_per_unit": 500000, "aggregate_only": True},
        "context": {"candidate_chars": context_chars, "candidate_token_estimate": math.ceil(context_chars / 4) if context_chars else 0, "repeated_candidate_chars": repeated_context_chars, "repeated_token_estimate": math.ceil(repeated_context_chars / 4) if repeated_context_chars else 0, "repeated_candidate_ratio": repetition_ratio, "repeated_line_candidates": repeated_lines},
        "retry": {"configured_upper_bound_attempts": max(retry_bounds) if retry_bounds else None, "observed_config_count": len(retry_bounds)},
        "cache": {"cacheable_candidate_chars": cache_candidate_chars, "repeated_payload_candidate": bool(cache_candidate_chars and repeated_context_chars)},
        "budget": {"declared_values": sorted(set(budget_values))[:20], "count": len(budget_values)},
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
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")[:2_000_000]
        except OSError:
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
        "target_repository": args.target_repository,
        "target_ref": args.target_ref,
        "target_commit": commit,
        "target_fingerprint": fingerprint,
        "static_precheck": {"canonical_signal_counts": canonical or counts, "aggregate_counts": canonical or counts, "raw_scan_counts": counts, "action_report": static, "canonical_source": "TARGET_STATIC_PRECHECK", "not_billing_or_savings": True},
        "provider_contract": detection["selected"],
        "provider_detection": detection,
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
