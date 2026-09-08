#!/usr/bin/env python3
"""Independent, sanitized validator for the public Stage 2 report.

This process does not trust the report's provider or grade.  It recomputes
provider/model/pricing equality, the L3 delta gate and per-finding evidence
levels from the binding, preflight and report JSON files.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


LEVEL_ORDER = {"L1_STRUCTURAL_DIAGNOSIS": 1, "L2_DETERMINISTIC_MEASUREMENT": 2, "L3_ESTIMATED_COST_SAVINGS": 3, "L4_PROVIDER_REPORTED_USAGE": 4, "L5_VERIFIED_SAVINGS": 5}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON_OBJECT_REQUIRED:{path.name}")
    return value


def _delta_invariant(context: dict[str, Any]) -> tuple[bool, bool]:
    """Return (has_measurement_fields, valid) without trusting truthiness."""
    keys = ("before_token_estimate", "candidate_token_estimate", "optimized_token_estimate", "avoidable_delta_tokens", "repeated_token_estimate")
    present = any(context.get(key) is not None for key in keys)
    if not present:
        return False, True
    try:
        before = int(context.get("before_token_estimate", context.get("candidate_token_estimate")))
        optimized = int(context.get("optimized_token_estimate"))
        delta = int(context.get("avoidable_delta_tokens", context.get("repeated_token_estimate")))
    except (TypeError, ValueError):
        return True, False
    valid = before >= 0 and optimized >= 0 and delta >= 0 and delta <= before and before - optimized == delta
    status = (context.get("delta_invariant") or {}).get("status")
    if status == "FAIL":
        valid = False
    return True, valid


def validate(binding: dict[str, Any], preflight: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    contract = dict(binding.get("provider_contract") or {})
    provider = contract.get("provider")
    model = contract.get("model")
    status = str(contract.get("provider_identity_status") or (binding.get("provider_resolution") or {}).get("status") or "DETECTED")
    pricing = dict(preflight.get("pricing_evidence") or {})
    price_binding = dict(preflight.get("pricing_binding") or {})
    endpoint = str(contract.get("endpoint") or contract.get("base_url") or "")
    tool_commit = str(binding.get("tool_commit") or "")
    target_commit = str(binding.get("target_commit") or "")
    if tool_commit and target_commit and tool_commit != "UNKNOWN" and target_commit != "UNKNOWN" and tool_commit == target_commit:
        failures.append("TOOL_TARGET_COMMIT_COLLISION")
    report_target = dict(report.get("target_binding") or {})
    if report_target and report_target.get("commit") and target_commit and report_target.get("commit") != target_commit:
        failures.append("TARGET_COMMIT_REPORT_BINDING_MISMATCH")
    pricing_equality = bool(
        pricing.get("provider") == provider
        and pricing.get("model") == model
        and price_binding.get("strict_equality") is not False
        and preflight.get("pricing_status") in {"PROVIDER_PUBLISHED", "CUSTOMER_CONTRACT", "EXPLICIT_ZERO"}
    )
    if pricing and (pricing.get("provider") != provider or pricing.get("model") != model):
        failures.append("PROVIDER_MODEL_PRICING_MISMATCH")
    if status != "DETECTED" and report.get("trust_level") in {"L3_ESTIMATED_COST_SAVINGS", "L5_VERIFIED_SAVINGS"}:
        failures.append("AMBIGUOUS_PROVIDER_PRICING_PROMOTED")
    if endpoint and "api.upstage.ai" in endpoint.lower() and pricing.get("provider") == "openai":
        failures.append("UPSTAGE_ENDPOINT_OPENAI_PRICING_FALSE_PASS")
    measurement = dict(binding.get("deterministic_measurement") or {})
    context = dict(measurement.get("context") or {})
    has_context_measurement, valid_context_delta = _delta_invariant(context)
    try:
        before = int(context.get("before_token_estimate", context.get("candidate_token_estimate")) or 0)
        optimized = int(context.get("optimized_token_estimate") or 0)
        delta = int(context.get("avoidable_delta_tokens", context.get("repeated_token_estimate")) or 0)
    except (TypeError, ValueError):
        before = optimized = delta = 0
    has_delta = valid_context_delta and before > 0 and optimized >= 0 and delta > 0
    if report.get("trust_level") == "L2_DETERMINISTIC_MEASUREMENT" and has_context_measurement and not valid_context_delta:
        failures.append("L2_DETERMINISTIC_DELTA_INVARIANT_FAILED")
    pricing_required = report.get("trust_level") in {"L3_ESTIMATED_COST_SAVINGS", "L5_VERIFIED_SAVINGS"} or report.get("verdict") in {"ESTIMATED_SAVINGS", "VERIFIED_SAVINGS"}
    if report.get("verdict") == "ESTIMATED_SAVINGS" and not (pricing_equality and status == "DETECTED" and has_delta):
        failures.append("ESTIMATED_SAVINGS_WITHOUT_STRICT_DELTA")
    findings = list((report.get("stage2_diagnosis") or {}).get("findings") or [])
    stage2_status = str((report.get("stage2_diagnosis") or {}).get("status") or "COMPLETE_STAGE2")
    if stage2_status not in {"COMPLETE_STAGE2", "PARTIAL_STAGE1_ONLY", "FAILED_INPUT", "FAILED_INTERNAL"}:
        failures.append("UNKNOWN_STAGE2_STATUS")
    if stage2_status != "COMPLETE_STAGE2" and report.get("trust_level") in {"L2_DETERMINISTIC_MEASUREMENT", "L3_ESTIMATED_COST_SAVINGS", "L4_PROVIDER_REPORTED_USAGE", "L5_VERIFIED_SAVINGS"}:
        failures.append("PARTIAL_STAGE2_PROMOTED")
    retry_evidence = dict((measurement.get("retry") or {}))
    for finding in findings:
        level = str(finding.get("verification_level") or "L1_STRUCTURAL_DIAGNOSIS")
        if level not in LEVEL_ORDER:
            failures.append(f"UNKNOWN_FINDING_LEVEL:{finding.get('rule')}")
            continue
        if level in {"L2_DETERMINISTIC_MEASUREMENT", "L3_ESTIMATED_COST_SAVINGS", "L4_PROVIDER_REPORTED_USAGE", "L5_VERIFIED_SAVINGS"} and not finding.get("deterministic_measurement"):
            failures.append(f"FINDING_LEVEL_WITHOUT_MEASUREMENT:{finding.get('rule')}")
        if finding.get("rule") == "RETRY_LOOP" and level in {"L2_DETERMINISTIC_MEASUREMENT", "L3_ESTIMATED_COST_SAVINGS"} and not (measurement.get("observed_retry_count") or measurement.get("measured_attempts")):
            failures.append("RETRY_PROMOTED_WITHOUT_OBSERVED_MEASUREMENT")
        if finding.get("rule") == "RETRY_LOOP" and retry_evidence.get("negative_evidence") == "RETRY_DISABLED_OBSERVED" and finding.get("impact_level") == "HIGH":
            failures.append("DISABLED_RETRY_MARKED_HIGH")
        if finding.get("source_category") == "DOCS_EXAMPLE" and finding.get("signal_confidence") == "WEAK" and int(finding.get("priority") or 99) == 1:
            failures.append("DOCS_WEAK_SIGNAL_TOP1")
        if finding.get("rule") == "CACHE_SIGNAL" and (measurement.get("cache") or {}).get("ordinary_cache_occurrences") and not (measurement.get("cache") or {}).get("llm_relevant_occurrences") and level != "L1_STRUCTURAL_DIAGNOSIS":
            failures.append("ORDINARY_CACHE_PROMOTED")
    safety = measurement.get("execution") or {}
    safety_zero = safety.get("provider_calls", 0) == 0 and safety.get("target_code_executed") is False and safety.get("secret_used") is False
    if not safety_zero:
        failures.append("FREE_PATH_SAFETY_BOUNDARY_FAILED")
    if status == "MULTIPLE_PROVIDERS" and report.get("trust_level") == "L3_ESTIMATED_COST_SAVINGS":
        failures.append("MULTI_PROVIDER_GLOBAL_PRICE_FALSE_PASS")
    # A free/secretless Stage 2 run may still resolve an official pricing row,
    # but it must not use that row for a savings claim without provider usage.
    # Presence of a matching, unused row is safe; only a mismatch is a false
    # pass and is already recorded above.
    pricing_safe = (not pricing) or pricing_equality
    checks = {
        "tool_target_commit_separate": "TOOL_TARGET_COMMIT_COLLISION" not in failures,
        "target_commit_report_binding": "TARGET_COMMIT_REPORT_BINDING_MISMATCH" not in failures,
        "target_endpoint_provider_model_recomputed": bool((provider and (model or status in {"MULTIPLE_PROVIDERS", "OPENAI_COMPATIBLE_CUSTOM"})) or (not provider and status == "UNKNOWN_PROVIDER")),
        "pricing_provider_model_strict_equality": pricing_equality if pricing_required else pricing_safe,
        "provider_conflicts_clear": (status == "MULTIPLE_PROVIDERS" and not pricing_required) or (not contract.get("conflicts") and status not in {"AMBIGUOUS_PROVIDER"}),
        # L2 structural/deterministic reports intentionally have no billed
        # Before/After delta.  Enforce the delta only when the report claims
        # an estimated or verified cost-saving level.
        "l2_delta_invariant": (report.get("trust_level") != "L2_DETERMINISTIC_MEASUREMENT") or (not has_context_measurement) or valid_context_delta,
        "l3_delta_gate": (not pricing_required) or has_delta,
        "per_finding_levels_safe": not any(item.startswith("FINDING_LEVEL") or item.startswith("RETRY_PROMOTED") for item in failures),
        "free_path_zero_execution": safety_zero,
        "multi_provider_not_forced": status != "MULTIPLE_PROVIDERS" or report.get("trust_level") != "L3_ESTIMATED_COST_SAVINGS",
        "stage2_status_accurate": stage2_status == "COMPLETE_STAGE2" or report.get("trust_level") == "L1_STRUCTURAL_DIAGNOSIS",
    }
    return {
        "schema": "costdoctor.public-stage2-independent-validation.r4.v1",
        "target_repository": binding.get("target_repository"),
        "target_commit": binding.get("target_commit"),
        "tool_repository": binding.get("tool_repository"),
        "tool_commit": binding.get("tool_commit"),
        "resolved_provider": provider,
        "resolved_model": model,
        "resolved_endpoint": endpoint or None,
        "pricing_provider": pricing.get("provider"),
        "pricing_model": pricing.get("model"),
        "provider_identity_status": status,
        "checks": checks,
        "failures": sorted(set(failures)),
        "verdict": "PASS" if not failures and all(checks.values()) else "FAIL",
        "actual_provider_savings": "UNVERIFIED_UNLESS_PROVIDER_RECEIPT_AND_QUALITY_PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate(load(args.binding), load(args.preflight), load(args.report))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": result["verdict"], "failure_count": len(result["failures"])}, ensure_ascii=False, sort_keys=True))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
