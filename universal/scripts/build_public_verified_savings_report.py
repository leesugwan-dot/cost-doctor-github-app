#!/usr/bin/env python3
"""Build the universal two-stage, sanitized user report.

Stage 2 never stops merely because a provider Secret is absent. It returns a
structural diagnosis and bounded estimated opportunities, while an actual
provider receipt can promote the same schema to VERIFIED_SAVINGS.
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


PHASES = ("raw", "engine", "engine_costdoctor")
LEVEL_ORDER = {
    "L1_STRUCTURAL_DIAGNOSIS": 1,
    "L2_DETERMINISTIC_MEASUREMENT": 2,
    "L3_ESTIMATED_COST_SAVINGS": 3,
    "L4_PROVIDER_REPORTED_USAGE": 4,
    "L5_VERIFIED_SAVINGS": 5,
}
RULE_TEXT = {
    "MODEL_CALL": ("모델/API 호출 문제", "중복·직렬 호출을 같은 입력 기준으로 묶고 실제 호출 수를 측정하세요.", "MEDIUM"),
    "RETRY_LOOP": ("재시도 증폭 문제", "일시 오류만 제한적으로 재시도하고 멱등 키와 재작업 비용을 기록하세요.", "HIGH"),
    "CACHE_SIGNAL": ("캐시 정책 문제", "테넌트·권한·모델별 캐시 키와 적중률을 측정하세요.", "MEDIUM"),
    "TOKEN_LIMIT": ("토큰/문맥 예산 문제", "필수 사실을 보존하는 최소 문맥과 출력 한도를 동일 품질로 비교하세요.", "MEDIUM"),
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON_OBJECT_REQUIRED:{path.name}")
    return payload


def d(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def money(value: Decimal) -> str:
    return f"{value:.9f}"


def _add_usage(target: dict[str, int], usage: dict[str, Any]) -> None:
    for key in ("input_tokens", "cached_input_tokens", "cache_write_tokens", "output_tokens", "reasoning_tokens", "total_tokens", "call_count", "retry_count", "tool_calls"):
        target[key] = target.get(key, 0) + int(usage.get(key, 0) or 0)


def fixture_reference(optimizer_dir: Path, acceptance: dict[str, Any]) -> dict[str, Any]:
    stages: dict[str, dict[str, Any]] = {phase: {"cost_usd": Decimal("0"), "usage": {}, "quality_sum": Decimal("0"), "quality_count": 0, "workloads": 0} for phase in PHASES}
    for child in sorted(optimizer_dir.iterdir() if optimizer_dir.exists() else []):
        packet_path = child / "three_stage.json"
        if not packet_path.exists():
            continue
        packet = load_json(packet_path)
        for phase, row in stages.items():
            phase_payload = packet.get("phases", {}).get(phase, {})
            row["cost_usd"] += d(phase_payload.get("metrics", {}).get("total_cost_usd"))
            _add_usage(row["usage"], phase_payload.get("metrics", {}).get("usage", {}))
            row["quality_sum"] += d(phase_payload.get("metrics", {}).get("quality_mean"))
            row["quality_count"] += 1
            row["workloads"] += 1
    rendered: dict[str, Any] = {}
    for phase, row in stages.items():
        rendered[phase] = {"cost_usd": money(row["cost_usd"]), "usage": row["usage"], "quality_mean": float(row["quality_sum"] / row["quality_count"]) if row["quality_count"] else None, "workloads": row["workloads"], "provider_reported": False, "measurement_grade": "BYTE_PROXY", "trust_level": "LOCAL_FIXTURE_REFERENCE_ONLY", "claim_scope": "ENGINE_SELF_TEST/PROVIDER_REFERENCE"}
    return {"status": "PASS_REFERENCE_ONLY" if acceptance.get("local_verdict") == "PASS" else "FAIL", "measurement_grade": "BYTE_PROXY", "provider_actual": False, "pricing_source": "deterministic fixture; not an external provider price", "stages": rendered, "false_pass_block": True, "claim_scope": "ENGINE_SELF_TEST/PROVIDER_REFERENCE"}


def _contract(binding: dict[str, Any] | None) -> dict[str, Any]:
    return dict((binding or {}).get("provider_contract") or {})


def provider_gate(preflight: dict[str, Any], provider_result: dict[str, Any] | None, binding: dict[str, Any] | None) -> dict[str, Any]:
    contract = _contract(binding)
    provider = contract.get("provider")
    model = contract.get("model")
    confidence = contract.get("confidence", "UNKNOWN")
    identity_status = str(contract.get("provider_identity_status") or "DETECTED")
    client_family = contract.get("client_family") or "unknown"
    identity_conflicts = list(contract.get("conflicts") or [])
    if provider in {"AMBIGUOUS_PROVIDER", "MULTIPLE_PROVIDERS", "OPENAI_COMPATIBLE_CUSTOM"}:
        identity_conflicts.append(f"UNPRICED_PROVIDER_{provider}")
    if not binding or not binding.get("target_fingerprint"):
        return {"status": "BLOCKED", "provider_authenticated": False, "verdict": "TARGET_BINDING_REQUIRED", "measurement_grade": "UNKNOWN", "verified_savings_available": False, "raw_secret_stored": False, "confidence": confidence, "client_family": client_family, "identity_conflicts": identity_conflicts}
    if provider_result is not None:
        same_binding = (
            provider_result.get("target_binding_fingerprint") == binding.get("target_fingerprint")
            and provider_result.get("target_repository") == binding.get("target_repository")
            and provider_result.get("target_commit") == binding.get("target_commit")
            and provider_result.get("workload_fingerprint") == ((binding.get("workload") or {}).get("fingerprint"))
            and provider_result.get("provider") == provider
            and (model is None or provider_result.get("model") == model)
        )
        authenticated = provider_result.get("provider_authenticated_verdict") == "PASS" and provider_result.get("pricing_status") in {"PROVIDER_PUBLISHED", "CUSTOMER_CONTRACT", "EXPLICIT_ZERO"} and same_binding and not identity_conflicts
        return {"status": "PASS" if authenticated else "BLOCKED", "provider_authenticated": authenticated, "verdict": "PASS" if authenticated else ("TARGET_BINDING_MISMATCH" if not same_binding else "UNKNOWN_PRICE_OR_PROVIDER_VERIFICATION"), "measurement_grade": provider_result.get("measurement_grade", "UNKNOWN"), "verified_savings_available": authenticated, "raw_secret_stored": False, "target_binding_match": same_binding, "provider": provider, "model": model, "confidence": confidence, "client_family": client_family, "identity_conflicts": identity_conflicts}
    if not provider:
        return {"status": "NOT_APPLICABLE", "provider_authenticated": False, "verdict": "NO_PROVIDER_DETECTED", "measurement_grade": "STRUCTURAL_ONLY", "verified_savings_available": False, "raw_secret_stored": False, "client_family": client_family, "identity_conflicts": identity_conflicts}
    if not preflight.get("credential_present", False):
        return {"status": "OPTIONAL_NOT_CONFIGURED", "provider_authenticated": False, "verdict": "SECRET_OPTIONAL_FOR_STAGE2", "measurement_grade": "STRUCTURAL_ONLY", "verified_savings_available": False, "raw_secret_stored": False, "provider": provider, "model": model, "credential_name": contract.get("credential_name"), "confidence": confidence, "client_family": client_family, "identity_conflicts": identity_conflicts}
    if not preflight.get("execution_confirmation_valid", False):
        return {"status": "BLOCKED_UNTIL_CONFIRMED", "provider_authenticated": False, "verdict": "PROVIDER_PAID_EXECUTION_APPROVED_REQUIRED", "measurement_grade": "STRUCTURAL_ONLY", "verified_savings_available": False, "raw_secret_stored": False, "provider": provider, "model": model, "confidence": confidence, "client_family": client_family, "identity_conflicts": identity_conflicts}
    return {"status": "BLOCKED", "provider_authenticated": False, "verdict": "PROVIDER_RESULT_MISSING", "measurement_grade": "UNKNOWN", "verified_savings_available": False, "raw_secret_stored": False, "provider": provider, "model": model, "confidence": confidence, "client_family": client_family, "identity_conflicts": identity_conflicts}


def _canonical_counts(static_report: dict[str, Any], binding: dict[str, Any] | None) -> dict[str, int]:
    precheck = (binding or {}).get("static_precheck") or {}
    values = precheck.get("canonical_signal_counts") or precheck.get("aggregate_counts") or {}
    findings = static_report.get("findings") or []
    if not values:
        values = {str(item.get("rule", "unknown")): int(item.get("signal_count", 0) or 0) for item in findings}
    # Preserve the scanner's key spelling for backward-compatible evidence;
    # consumers compare rule names case-insensitively below.
    return {str(key): int(value or 0) for key, value in values.items()}


def _measurement_for_rule(rule: str, measurement: dict[str, Any]) -> dict[str, Any] | None:
    context = measurement.get("context") or {}
    retry = measurement.get("retry") or {}
    cache = measurement.get("cache") or {}
    budget = measurement.get("budget") or {}
    if rule == "RETRY_LOOP" and retry.get("configured_upper_bound_attempts") is not None:
        return {"metric": "retry_upper_bound_attempts", "value": int(retry["configured_upper_bound_attempts"]), "unit": "attempts", "claim": "configured upper bound; not observed usage"}
    if rule == "CACHE_SIGNAL" and cache.get("cacheable_candidate_chars", 0):
        return {"metric": "cacheable_repetition_chars", "value": int(cache["cacheable_candidate_chars"]), "unit": "characters", "claim": "source repetition candidate; not cache hit rate"}
    if rule == "TOKEN_LIMIT" and budget.get("declared_values"):
        return {"metric": "declared_context_or_output_limits", "value": list(budget["declared_values"]), "unit": "configured token limit", "claim": "configuration evidence; not provider usage"}
    if rule in {"MODEL_CALL", "CACHE_SIGNAL", "TOKEN_LIMIT"} and (context.get("repeated_candidate_chars", 0) or context.get("repeated_token_estimate", 0)):
        return {"metric": "repeated_context_chars" if context.get("repeated_candidate_chars", 0) else "repeated_context_tokens", "value": int(context.get("repeated_candidate_chars") or context.get("repeated_token_estimate") or 0), "unit": "characters" if context.get("repeated_candidate_chars", 0) else "estimated tokens", "ratio": context.get("repeated_candidate_ratio", 0), "token_estimate": context.get("repeated_token_estimate"), "claim": "deterministic source structure; not billed tokens"}
    return None


def _provider_pricing_matches(preflight: dict[str, Any], contract: dict[str, Any]) -> bool:
    evidence = preflight.get("pricing_evidence") or {}
    binding = preflight.get("pricing_binding") or {}
    return bool(
        preflight.get("pricing_status") in {"PROVIDER_PUBLISHED", "CUSTOMER_CONTRACT", "EXPLICIT_ZERO"}
        and evidence.get("provider") == contract.get("provider")
        and evidence.get("model") == contract.get("model")
        and binding.get("strict_equality") is not False
        and str(contract.get("provider_identity_status") or "DETECTED") == "DETECTED"
        and not contract.get("conflicts")
    )


def _estimated_cost_effect(measurement: dict[str, Any], preflight: dict[str, Any], grade: str) -> dict[str, Any] | None:
    if grade != "L3_ESTIMATED_COST_SAVINGS":
        return None
    context = measurement.get("context") or {}
    tokens = int(context.get("avoidable_delta_tokens") or context.get("repeated_token_estimate") or 0)
    rates = ((preflight.get("pricing_evidence") or {}).get("unit_rates_usd") or {})
    if tokens <= 0 or rates.get("input_tokens") is None:
        return None
    per_call = (d(rates.get("input_tokens")) * d(tokens) / d(1_000_000)).quantize(Decimal("0.000000001"))
    return {"metric": "avoidable_input_cost_per_call", "value_usd": money(per_call), "input_tokens": tokens, "unit": "USD per hypothetical call", "claim": "official pricing plus deterministic before/optimized delta; not billed usage and no monthly extrapolation"}


def _pricing_bound_measurement(measurement: dict[str, Any]) -> bool:
    """Require a reproducible before/optimized quantity delta for L3."""
    context = measurement.get("context") or {}
    before = int(context.get("before_token_estimate") or context.get("candidate_token_estimate") or 0)
    optimized = int(context.get("optimized_token_estimate") or 0)
    delta = int(context.get("avoidable_delta_tokens") or 0)
    return before > 0 and optimized >= 0 and delta > 0 and before - optimized == delta


def _finding_level(rule: str, measurement: dict[str, Any] | None, *, actual_available: bool, global_grade: str) -> str:
    """Assign evidence per finding; a global report grade is never copied blindly."""
    if actual_available and global_grade == "L5_VERIFIED_SAVINGS":
        return "L5_VERIFIED_SAVINGS"
    if not measurement:
        return "L1_STRUCTURAL_DIAGNOSIS"
    # A configured retry ceiling is a structural clue, not observed usage.
    if rule == "RETRY_LOOP" and not (measurement.get("observed_retry_count") or measurement.get("measured_attempts")):
        return "L1_STRUCTURAL_DIAGNOSIS"
    if global_grade == "L3_ESTIMATED_COST_SAVINGS" and _pricing_bound_measurement({"context": measurement}):
        return "L3_ESTIMATED_COST_SAVINGS"
    return "L2_DETERMINISTIC_MEASUREMENT"


def _diagnosis(static_report: dict[str, Any], binding: dict[str, Any] | None, provider: dict[str, Any], evidence_level: str = "L1_STRUCTURAL_DIAGNOSIS", *, actual_available: bool = False) -> list[dict[str, Any]]:
    aggregate = _canonical_counts(static_report, binding)
    measurement = (binding or {}).get("deterministic_measurement") or {}
    contract = (binding or {}).get("provider_contract") or {}
    result: list[dict[str, Any]] = []
    for key, (title, recommendation, impact) in RULE_TEXT.items():
        aliases = {key, key.lower(), key.replace("_", "-").lower(), key.lower() + "_signals"}
        if key == "MODEL_CALL":
            aliases.update({"model_call_signals", "model_calls"})
        elif key == "RETRY_LOOP":
            aliases.update({"retry_signals", "retry_loop"})
        elif key == "CACHE_SIGNAL":
            aliases.update({"cache_signals", "cache"})
        elif key == "TOKEN_LIMIT":
            aliases.update({"token_signals", "token_limit_signals", "context_signals"})
        aliases_lower = {str(alias).lower() for alias in aliases}
        count = sum(int(value or 0) for name, value in aggregate.items() if str(name).lower() in aliases_lower or str(name).upper() == key)
        if count <= 0:
            continue
        measurement_value = _measurement_for_rule(key, measurement)
        finding_level = _finding_level(key, measurement_value, actual_available=actual_available, global_grade=evidence_level)
        result.append({
            "priority": len(result) + 1,
            "rule": key,
            "problem": title,
            "canonical_signal_count": count,
            "canonical_source": "TARGET_STATIC_PRECHECK",
            "structural_evidence": {"source": "TARGET_REPOSITORY_CHECKOUT", "signal_count": count, "not_billing": True},
            "provider_detection_evidence": {"provider": contract.get("provider"), "model": contract.get("model"), "endpoint": contract.get("endpoint") or contract.get("base_url"), "client_family": contract.get("client_family"), "confidence": contract.get("confidence", "UNKNOWN"), "identity_source": contract.get("identity_source"), "conflicts": contract.get("conflicts", []), "raw_hits_internal_only": True},
            "deterministic_measurement": measurement_value,
            "evidence": {"signal_count": count, "source": "TARGET_STATIC_PRECHECK", "not_billing": True},
            "why_cost_grows": "반복 호출·재시도·불필요한 문맥이 실제 사용량을 늘릴 수 있습니다.",
            "improvement": recommendation,
            "impact_level": impact,
            "expected_impact": impact,
            "estimated_effect": measurement_value if finding_level in {"L2_DETERMINISTIC_MEASUREMENT", "L3_ESTIMATED_COST_SAVINGS", "L4_PROVIDER_REPORTED_USAGE", "L5_VERIFIED_SAVINGS"} else None,
            "estimated_savings_range": None,
            "verification_level": finding_level,
            "provider_detected": provider.get("provider") or "UNKNOWN",
        })
    if not result:
        result.append({"priority": 1, "rule": "NO_CANDIDATE", "problem": "명확한 비용 구조 후보 없음", "canonical_signal_count": 0, "canonical_source": "TARGET_STATIC_PRECHECK", "structural_evidence": {"source": "TARGET_REPOSITORY_CHECKOUT", "signal_count": 0, "not_billing": True}, "provider_detection_evidence": {"provider": contract.get("provider"), "model": contract.get("model"), "confidence": contract.get("confidence", "UNKNOWN"), "raw_hits_internal_only": True}, "deterministic_measurement": None, "evidence": {"source": "TARGET_STATIC_PRECHECK", "signal_count": 0, "not_billing": True}, "why_cost_grows": "현재 범위에서 LLM 비용 신호가 확인되지 않았습니다.", "improvement": "실제 사용량 또는 안전한 workload descriptor가 있으면 동일 조건 측정을 추가하세요.", "impact_level": "LOW", "expected_impact": "LOW", "estimated_effect": None, "estimated_savings_range": None, "verification_level": evidence_level, "provider_detected": provider.get("provider") or "UNKNOWN"})
    return result[:5]


def build_report(static_report: dict[str, Any], acceptance: dict[str, Any], optimizer_dir: Path, preflight: dict[str, Any], provider_result: dict[str, Any] | None, active_project: str | None = None, target_binding: dict[str, Any] | None = None, target_precheck: dict[str, Any] | None = None) -> dict[str, Any]:
    binding = target_binding or target_precheck
    if binding is None and active_project:
        binding = {"target_repository": active_project, "target_fingerprint": None, "provider_contract": {}, "static_precheck": {"aggregate_counts": {}}, "workload": {"ready": False, "reason": "TARGET_BINDING_EVIDENCE_REQUIRED"}}
    fixture = fixture_reference(optimizer_dir, acceptance)
    provider = provider_gate(preflight, provider_result, binding)
    actual_available = bool(provider.get("verified_savings_available"))
    aggregate = _canonical_counts(static_report, binding)
    detected = provider.get("provider") or _contract(binding).get("provider")
    workload = (binding or {}).get("workload") or {}
    deterministic_evidence = (binding or {}).get("deterministic_measurement") or {}
    deterministic = bool(deterministic_evidence.get("available") or workload.get("ready"))
    contract = _contract(binding)
    confidence = str(contract.get("confidence") or preflight.get("provider_confidence") or "UNKNOWN").upper()
    priced = _provider_pricing_matches(preflight, contract)
    if actual_available:
        grade, verdict = "L5_VERIFIED_SAVINGS", "VERIFIED_SAVINGS"
    elif priced and deterministic and _pricing_bound_measurement(deterministic_evidence) and confidence in {"STRONG", "MEDIUM"} and contract.get("model"):
        grade, verdict = "L3_ESTIMATED_COST_SAVINGS", "ESTIMATED_SAVINGS"
    else:
        grade, verdict = ("L2_DETERMINISTIC_MEASUREMENT", "DETERMINISTIC_MEASUREMENT") if deterministic else ("L1_STRUCTURAL_DIAGNOSIS", "STRUCTURAL_DIAGNOSIS")
    reported = provider_result.get("stages") if actual_available and provider_result else {phase: None for phase in PHASES}
    diagnosis = _diagnosis(static_report, binding, provider, grade, actual_available=actual_available)
    finding_levels = {item.get("rule"): item.get("verification_level") for item in diagnosis}
    distinct_levels = sorted({value for value in finding_levels.values() if value}, key=lambda value: LEVEL_ORDER.get(value, 0))
    level_labels = {"L1_STRUCTURAL_DIAGNOSIS": "구조 분석", "L2_DETERMINISTIC_MEASUREMENT": "결정론적 정량측정", "L3_ESTIMATED_COST_SAVINGS": "공식 가격 기반 추정", "L5_VERIFIED_SAVINGS": "실제 사용량 검증"}
    verification_label = f"혼합 ({'~'.join(level_labels.get(value, value) for value in distinct_levels)})" if len(distinct_levels) > 1 else level_labels.get(grade, grade)
    estimated_cost_effect = _estimated_cost_effect(deterministic_evidence, preflight, grade)
    summary = {
        "what_wasted": diagnosis,
        "what_changed": ["Stage 1 정적 precheck 결과를 Stage 2 진단 후보로 확장", "target checkout의 runner-local shadow에서만 측정 후보를 구성", "정적·fixture 수치는 실제 청구 절감으로 승격하지 않음"],
        "before_cost": "UNKNOWN" if not actual_available else provider_result.get("stages", {}).get("raw", {}).get("cost_usd"),
        "after_cost": "UNKNOWN" if not actual_available else provider_result.get("stages", {}).get("engine_costdoctor", {}).get("cost_usd"),
        "savings_rate": "UNKNOWN" if not actual_available else provider_result.get("savings", {}).get("total_fraction"),
        "tokens_usage": "PROVIDER_REPORTED_USAGE" if actual_available else ((deterministic_evidence.get("context") or {}).get("token_estimate") and "DETERMINISTIC_TOKEN_ESTIMATE (not provider usage)" or "정적 구조만 확인"),
        "quality": "NON_REGRESSION_VERIFIED" if actual_available else "코드 실행 없이 안전 분석 완료",
        "verification_cost": "UNKNOWN" if not actual_available else provider_result.get("validation_overhead_usd", "UNKNOWN"),
        "net_saving": "UNKNOWN" if not actual_available else provider_result.get("net_saving_usd", "UNKNOWN"),
        "verification_label": verification_label,
        "deterministic_measurement": deterministic_evidence if deterministic else None,
        "estimated_cost_effect": estimated_cost_effect,
    }
    return {
        "schema": "costdoctor.public-verified-savings.universal-stage2.v3",
        "report_schema_version": "3.0.0",
        "verdict": verdict,
        "trust_level": grade,
        "target_binding": {"repository": (binding or {}).get("target_repository"), "ref": (binding or {}).get("target_ref"), "commit": (binding or {}).get("target_commit"), "fingerprint": (binding or {}).get("target_fingerprint"), "provider_contract": _contract(binding), "workload": {key: value for key, value in workload.items() if key not in {"prompt", "items"}}, "bound": bool(binding and binding.get("target_fingerprint"))},
        "static_precheck": {"status": "PASS" if binding else "UNKNOWN", "canonical_signal_counts": aggregate, "signal_counts": aggregate, "canonical_source": "TARGET_STATIC_PRECHECK", "source": "TARGET_REPOSITORY_CHECKOUT" if binding else "UNBOUND", "not_billing_or_savings": True},
        "stage2_diagnosis": {"status": "PASS", "evidence_level": grade, "finding_evidence_levels": finding_levels, "mixed_evidence": len(distinct_levels) > 1, "evidence_levels_present": distinct_levels, "provider_detected": detected, "provider_confidence": confidence, "provider_candidates": ((binding or {}).get("provider_detection") or {}).get("provider_candidates", []), "provider_groups": ((binding or {}).get("provider_detection") or {}).get("provider_groups", []), "findings": diagnosis, "secretless_continuation": True, "raw_detector_hits_user_visible": False},
        "fixture_reference": fixture,
        "provider": {**provider, "pricing_bound": priced, "pricing_binding": preflight.get("pricing_binding") or {}},
        "reported_stages": reported,
        "reported_stage_reason": "PROVIDER_AUTHENTICATED_TARGET_RECEIPT" if actual_available else "Provider usage is optional; structural/estimated Stage 2 remains available and fixture claims are excluded.",
        "quality": {"provider_before": provider_result.get("stages", {}).get("raw", {}).get("quality") if provider_result else None, "provider_after": provider_result.get("stages", {}).get("engine_costdoctor", {}).get("quality") if provider_result else None, "fixture_quality_non_regression": all(row.get("quality", {}).get("failed_phases", []) == [] for row in acceptance.get("workloads", [])), "target_workload_ready": deterministic, "verdict": "PASS" if actual_available else "NOT_MEASURED_PROVIDER"},
        "validation_overhead": {"optimizer_monetary_cost_usd": "0.000000000", "provider_validation_cost_usd": None if not actual_available else provider_result.get("validation_overhead_usd"), "rollback_reapply_included": bool(provider_result and provider_result.get("rollback", {}).get("actual_status") == "PASS"), "net_saving_usd": None if not actual_available else summary["net_saving"], "break_even": "UNKNOWN" if not actual_available else provider_result.get("break_even", "UNKNOWN")},
        "user_summary": summary,
        "false_pass_guards": {"target_binding_required": True, "static_not_promoted": True, "canonical_count_single_source": True, "raw_detector_hits_internal_only": True, "byte_proxy_not_provider_usage": True, "unknown_price_blocked": True, "different_workload_blocked": True, "quality_drop_blocks": True, "spend_cap_enforced": True, "raw_secret_output": False, "raw_target_source_output": False, "shadow_repo_write": False, "fixture_not_target": True, "provider_is_registry_selected": True, "secret_optional_for_stage2": True, "target_code_execution": False, "provider_network_calls": False},
        "user_action_queue": [],
    }


def render_markdown(report: dict[str, Any]) -> str:
    target = report["target_binding"]
    summary = report["user_summary"]
    level_label = summary.get("verification_label", report["trust_level"])
    static_counts = report.get("static_precheck", {}).get("canonical_signal_counts", {})
    provider_verified = bool((report.get("provider") or {}).get("provider_authenticated"))
    api_line = "- 실제 API 호출: **provider 영수증으로 확인됨**" if provider_verified else "- 실제 API 호출: **없음 (무료 공개 진단)**"
    provider_payload = report.get("provider") or {}
    contract = target.get("provider_contract") or {}
    provider_name = provider_payload.get("provider") or contract.get("provider")
    if provider_name in {"AMBIGUOUS_PROVIDER", "MULTIPLE_PROVIDERS", "OPENAI_COMPATIBLE_CUSTOM"} or not provider_name:
        provider_line = "- 감지 Provider: **정확히 확정하지 못함** (가격 추정 생략)"
    else:
        client = contract.get("client_family") or provider_payload.get("client_family") or "unknown"
        model = contract.get("model") or "UNKNOWN_MODEL"
        provider_line = f"- 감지 Provider: **{provider_name}** · 사용 Client: **{client}** · 모델: **{model}**"
    risk_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    risk = max((item.get("impact_level", "LOW") for item in summary["what_wasted"]), key=lambda value: risk_order.get(value, 0))
    lines = [
        "# CostDoctor 결과", "", "## 한눈에 보기", "",
        f"- 비용 위험: **{risk}**", f"- 검증 수준: **{level_label}**",
        f"- 대상: `{target.get('repository') or 'UNKNOWN'}` / `{target.get('commit') or 'UNKNOWN'}`",
        provider_line, api_line, "",
        "### Stage 1 canonical 신호 (Stage 2도 이 숫자를 그대로 사용)", "",
        "| 문제 유형 | 후보 수 |", "| --- | ---: |",
    ]
    labels = {"MODEL_CALL": "모델 호출 후보", "RETRY_LOOP": "재시도 후보", "CACHE_SIGNAL": "캐시 후보", "TOKEN_LIMIT": "토큰·문맥 후보"}
    for key in ("MODEL_CALL", "RETRY_LOOP", "CACHE_SIGNAL", "TOKEN_LIMIT"):
        matching = next((value for name, value in static_counts.items() if str(name).upper() == key), None)
        if matching is not None:
            lines.append(f"| {labels[key]} | {int(matching)} |")
    lines.extend(["", "## 주요 문제", ""])
    for item in summary["what_wasted"]:
        measurement = item.get("deterministic_measurement")
        measurement_text = "정량 측정 전"
        if measurement:
            metric = measurement.get("metric", "구조 측정")
            value = measurement.get("value")
            unit = measurement.get("unit", "")
            measurement_text = f"{metric}: {value} {unit} (청구 비용 아님)"
        lines.extend([
            f"### {item['priority']}. {item['problem']}",
            f"- 발견 근거: **{item['canonical_signal_count']}개 후보** (Stage 1 canonical)",
            f"- 왜 비용 문제인가: {item['why_cost_grows']}",
            f"- 구체적 개선방법: {item['improvement']}",
            f"- 현재 영향: **{item['impact_level']}**",
            f"- 정량 측정: **{measurement_text}**",
            "- 예상 효과: **근거가 있을 때만 표시**",
            f"- 검증 수준: **{item['verification_level']}**", "",
        ])
    cost_effect = summary.get("estimated_cost_effect")
    if cost_effect:
        cost_line = f"- 공식 가격에 결속한 구조 추정: **${cost_effect['value_usd']} / 가상 호출 1회** (청구 비용·월간 환산 아님)"
    else:
        cost_line = "- 공식 가격 결속 비용 추정: **측정하지 않음**"
    lines.extend([
        "## 비용·토큰",
        f"- 실제 Provider 비용: **{'측정하지 않음' if summary['before_cost'] == 'UNKNOWN' else summary['before_cost']}**",
        f"- 실제 절감률: **{'측정하지 않음' if summary['savings_rate'] == 'UNKNOWN' else summary['savings_rate']}**",
        "- 검증되지 않은 실제 절감률: **UNKNOWN_UNTIL_MEASURED**",
        f"- 무료 분석에서 확인된 값: **{summary.get('tokens_usage', '정적 구조만 확인')}**",
        cost_line,
        "- 실제 API 호출 없이 분석했기 때문에 청구 비용 절감률은 계산하지 않았습니다." if not provider_verified else "- 비용·토큰 값은 provider가 반환한 사용량과 가격표에 결속됩니다.", "",
        "## 안전", "- 대상 코드 실행: **없음**", "- 모델 API 호출: **없음**",
        "- 고객 Repo 수정: **없음**", "- 원문 Source 외부전송: **없음**", "- Secret 요구/사용: **없음**", "",
        "## 더 높은 검증 수준",
        "Provider Secret이 없어도 무료 구조 분석은 완료됩니다. 실제 Provider 사용량이 연결된 고급 경로에서는 같은 결과 구조가 공식 사용량 검증으로 승격될 수 있습니다." if not provider_verified else "Provider 사용량 영수증과 품질 게이트가 확인된 결과입니다.", "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--static-report", type=Path, required=True)
    parser.add_argument("--optimizer-dir", type=Path, required=True)
    parser.add_argument("--provider-preflight", type=Path, required=True)
    parser.add_argument("--provider-result", type=Path)
    parser.add_argument("--active-project")
    parser.add_argument("--target-binding", type=Path)
    parser.add_argument("--target-precheck", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    static_report = load_json(args.static_report)
    acceptance = load_json(args.optimizer_dir / "acceptance.json")
    preflight = load_json(args.provider_preflight)
    provider_result = load_json(args.provider_result) if args.provider_result and args.provider_result.exists() else None
    binding = load_json(args.target_binding) if args.target_binding and args.target_binding.exists() else None
    target_precheck = load_json(args.target_precheck) if args.target_precheck and args.target_precheck.exists() else None
    report = build_report(static_report, acceptance, args.optimizer_dir, preflight, provider_result, args.active_project, binding, target_precheck)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "verified_savings_report.json").write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (args.output / "verified_savings_report.md").write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "trust_level": report["trust_level"], "provider_status": report["provider"]["status"], "target_bound": report["target_binding"]["bound"], "user_actions": len(report["user_action_queue"])}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
