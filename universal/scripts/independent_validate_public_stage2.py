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


def _request_bound_measurement(measurement: dict[str, Any]) -> bool:
    context = measurement.get("context") if isinstance(measurement.get("context"), dict) else measurement
    runtime = measurement.get("runtime") if isinstance(measurement.get("runtime"), dict) else {}
    call_group = str(measurement.get("call_group_id") or context.get("call_group_id") or "")
    payload_scope = str(measurement.get("payload_scope_id") or context.get("payload_scope_id") or "")
    before_scope = str(context.get("before_payload_scope") or "")
    optimized_scope = str(context.get("optimized_payload_scope") or "")
    paths = list(measurement.get("request_paths") or runtime.get("call_path_evidence") or [])
    return bool(call_group and payload_scope and before_scope and optimized_scope and any(isinstance(row, dict) and row.get("call_kind") == "runtime_invocation" for row in paths))


def _semantic_projection(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("user_summary") or {}
    diagnosis = report.get("stage2_diagnosis") or {}
    return {
        "trust_level": report.get("trust_level"),
        "verdict": report.get("verdict"),
        "priority": summary.get("optimization_priority"),
        "priority_reason": summary.get("priority_reason"),
        "measurement_states": summary.get("measurement_states") or diagnosis.get("measurement_states"),
        "findings": [
            {"id": row.get("finding_id"), "rule": row.get("rule"), "impact": row.get("impact_level"), "level": row.get("verification_level"), "runtime_cost_impact": row.get("runtime_cost_impact"), "claim": (row.get("deterministic_measurement") or {}).get("claim")}
            for row in diagnosis.get("findings") or []
        ],
        "actual_claim": {key: (summary.get(key) or report.get(key)) for key in ("before_cost", "after_cost", "savings_rate", "quality")},
    }


def validate(binding: dict[str, Any], preflight: dict[str, Any], report: dict[str, Any], report_en: dict[str, Any] | None = None) -> dict[str, Any]:
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
    request_bound = _request_bound_measurement(measurement)
    if report.get("verdict") == "ESTIMATED_SAVINGS" and not (pricing_equality and status == "DETECTED" and has_delta and request_bound):
        failures.append("ESTIMATED_SAVINGS_WITHOUT_STRICT_DELTA")
    if report.get("trust_level") == "L3_ESTIMATED_COST_SAVINGS" and not request_bound:
        failures.append("L3_REQUEST_PAYLOAD_BINDING_REQUIRED")
    findings = list((report.get("stage2_diagnosis") or {}).get("findings") or [])
    stage2_status = str((report.get("stage2_diagnosis") or {}).get("status") or "COMPLETE_STAGE2")
    if stage2_status not in {"COMPLETE_STAGE2", "PARTIAL_STAGE1_ONLY", "FAILED_INPUT", "FAILED_INTERNAL"}:
        failures.append("UNKNOWN_STAGE2_STATUS")
    if stage2_status != "COMPLETE_STAGE2" and report.get("trust_level") in {"L2_DETERMINISTIC_MEASUREMENT", "L3_ESTIMATED_COST_SAVINGS", "L4_PROVIDER_REPORTED_USAGE", "L5_VERIFIED_SAVINGS"}:
        failures.append("PARTIAL_STAGE2_PROMOTED")
    states = dict((report.get("stage2_diagnosis") or {}).get("measurement_states") or {})
    actual_available = bool((report.get("provider") or {}).get("provider_authenticated"))
    for required_state in ("structural_diagnosis", "actual_usage", "actual_cost", "actual_savings", "quality_non_regression"):
        if required_state not in states:
            failures.append(f"MEASUREMENT_STATE_MISSING:{required_state}")
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
        runtime_impact = dict(finding.get("runtime_impact") or {})
        if finding.get("rule") == "MODEL_CALL" and not int(runtime_impact.get("runtime_invocation_count") or 0) and finding.get("impact_level") == "HIGH":
            failures.append("NON_RUNTIME_MODEL_CALL_MARKED_HIGH")
        if finding.get("rule") == "MODEL_CALL" and finding.get("runtime_cost_impact") is True and not (request_bound or actual_available):
            failures.append("MODEL_CALL_EXISTENCE_PROMOTED_TO_WASTE")
        if finding.get("rule") == "CACHE_SIGNAL" and finding.get("runtime_cost_impact") is True and (measurement.get("cache") or {}).get("hit_rate") in {None, "UNKNOWN"}:
            failures.append("UNBOUND_CACHE_PROMOTED_TO_SAVINGS")
        action_plan = finding.get("action_plan") or {}
        if not all(action_plan.get(key) for key in ("ko", "en", "measure", "exclude")):
            failures.append("GENERIC_ACTION_WITHOUT_FINDING_CONTEXT")
        for location in finding.get("locations") or []:
            if not isinstance(location, dict) or str(location.get("relative_path") or "").startswith(("/", "\\")) or ":\\" in str(location.get("relative_path") or ""):
                failures.append("UNSAFE_FINDING_LOCATION")
            if isinstance(location, dict) and (location.get("source_category") in {"TEST_EVAL", "DOCS_EXAMPLE"} or location.get("call_kind") in {"test_eval_invocation", "docs_example_invocation"}):
                failures.append("USER_RUNTIME_LOCATION_CONTAINS_NON_PRODUCTION")
        for location in (finding.get("location_groups") or {}).get("runtime") or []:
            if location.get("source_category") in {"TEST_EVAL", "DOCS_EXAMPLE"} or location.get("call_kind") in {"test_eval_invocation", "docs_example_invocation"}:
                failures.append("USER_RUNTIME_LOCATION_CONTAINS_NON_PRODUCTION")
    safety = measurement.get("execution") or {}
    safety_zero = safety.get("provider_calls", 0) == 0 and safety.get("target_code_executed") is False and safety.get("secret_used") is False
    if not safety_zero:
        failures.append("FREE_PATH_SAFETY_BOUNDARY_FAILED")
    if status == "MULTIPLE_PROVIDERS" and report.get("trust_level") == "L3_ESTIMATED_COST_SAVINGS":
        failures.append("MULTI_PROVIDER_GLOBAL_PRICE_FALSE_PASS")
    provider_authenticated = bool((report.get("provider") or {}).get("provider_authenticated"))
    if not provider_authenticated and report.get("trust_level") in {"L4_PROVIDER_REPORTED_USAGE", "L5_VERIFIED_SAVINGS"}:
        failures.append("PROVIDER_USAGE_ABSENCE_MISCLASSIFIED_AS_IMPLEMENTATION_FAILURE")
    summary = report.get("user_summary") or {}
    if summary.get("optimization_priority") in {"높음", "High"} and not any(item.get("runtime_cost_impact") is True for item in findings):
        failures.append("HIGH_WITHOUT_RUNTIME_COST_IMPACT")
    if report_en is not None and _semantic_projection(report) != _semantic_projection(report_en):
        failures.append("KO_EN_CLAIM_LEVEL_MISMATCH")
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
        "l3_delta_gate": (not pricing_required) or (has_delta and request_bound),
        "per_finding_levels_safe": not any(item.startswith("FINDING_LEVEL") or item.startswith("RETRY_PROMOTED") for item in failures),
        "free_path_zero_execution": safety_zero,
        "multi_provider_not_forced": status != "MULTIPLE_PROVIDERS" or report.get("trust_level") != "L3_ESTIMATED_COST_SAVINGS",
        "stage2_status_accurate": stage2_status == "COMPLETE_STAGE2" or report.get("trust_level") == "L1_STRUCTURAL_DIAGNOSIS",
        "measurement_states_separated": not any(item.startswith("MEASUREMENT_STATE_MISSING") for item in failures),
        "non_runtime_not_high": "NON_RUNTIME_MODEL_CALL_MARKED_HIGH" not in failures,
        "finding_locations_safe": "UNSAFE_FINDING_LOCATION" not in failures,
        "l3_request_payload_binding": "L3_REQUEST_PAYLOAD_BINDING_REQUIRED" not in failures,
        "high_priority_has_runtime_cost_impact": "HIGH_WITHOUT_RUNTIME_COST_IMPACT" not in failures,
        "runtime_locations_production_only": "USER_RUNTIME_LOCATION_CONTAINS_NON_PRODUCTION" not in failures,
        "actionable_findings": "GENERIC_ACTION_WITHOUT_FINDING_CONTEXT" not in failures,
        "unbound_cache_not_promoted": "UNBOUND_CACHE_PROMOTED_TO_SAVINGS" not in failures,
        "model_call_not_promoted_by_existence": "MODEL_CALL_EXISTENCE_PROMOTED_TO_WASTE" not in failures,
        "provider_absence_is_normal_free_state": "PROVIDER_USAGE_ABSENCE_MISCLASSIFIED_AS_IMPLEMENTATION_FAILURE" not in failures,
        "ko_en_claim_level_parity": "KO_EN_CLAIM_LEVEL_MISMATCH" not in failures,
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
        "canonical_semantics": _semantic_projection(report),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--report-en", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate(load(args.binding), load(args.preflight), load(args.report), load(args.report_en) if args.report_en and args.report_en.exists() else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": result["verdict"], "failure_count": len(result["failures"])}, ensure_ascii=False, sort_keys=True))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
