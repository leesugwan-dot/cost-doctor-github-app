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
RULE_TEXT = {
    "MODEL_CALL": ("모델/API 호출 후보", "중복·직렬 호출을 같은 입력 기준으로 묶고 실제 호출 수를 측정하세요.", "MEDIUM", "5~25%"),
    "RETRY_LOOP": ("재시도 증폭 후보", "일시 오류만 제한적으로 재시도하고 멱등 키와 재작업 비용을 기록하세요.", "HIGH", "0~30%"),
    "CACHE_SIGNAL": ("캐시 정책 후보", "테넌트·권한·모델별 캐시 키와 적중률을 측정하세요.", "MEDIUM", "5~20%"),
    "TOKEN_LIMIT": ("토큰/문맥 예산 후보", "필수 사실을 보존하는 최소 문맥과 출력 한도를 동일 품질로 비교하세요.", "MEDIUM", "5~35%"),
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
    if not binding or not binding.get("target_fingerprint"):
        return {"status": "BLOCKED", "provider_authenticated": False, "verdict": "TARGET_BINDING_REQUIRED", "measurement_grade": "UNKNOWN", "verified_savings_available": False, "raw_secret_stored": False}
    if provider_result is not None:
        same_binding = (
            provider_result.get("target_binding_fingerprint") == binding.get("target_fingerprint")
            and provider_result.get("target_repository") == binding.get("target_repository")
            and provider_result.get("target_commit") == binding.get("target_commit")
            and provider_result.get("workload_fingerprint") == ((binding.get("workload") or {}).get("fingerprint"))
            and provider_result.get("provider") == provider
            and (model is None or provider_result.get("model") == model)
        )
        authenticated = provider_result.get("provider_authenticated_verdict") == "PASS" and provider_result.get("pricing_status") in {"PROVIDER_PUBLISHED", "CUSTOMER_CONTRACT", "EXPLICIT_ZERO"} and same_binding
        return {"status": "PASS" if authenticated else "BLOCKED", "provider_authenticated": authenticated, "verdict": "PASS" if authenticated else ("TARGET_BINDING_MISMATCH" if not same_binding else "UNKNOWN_PRICE_OR_PROVIDER_VERIFICATION"), "measurement_grade": provider_result.get("measurement_grade", "UNKNOWN"), "verified_savings_available": authenticated, "raw_secret_stored": False, "target_binding_match": same_binding, "provider": provider, "model": model}
    if not provider:
        return {"status": "NOT_APPLICABLE", "provider_authenticated": False, "verdict": "NO_PROVIDER_DETECTED", "measurement_grade": "STRUCTURAL_ONLY", "verified_savings_available": False, "raw_secret_stored": False}
    if not preflight.get("credential_present", False):
        return {"status": "OPTIONAL_NOT_CONFIGURED", "provider_authenticated": False, "verdict": "SECRET_OPTIONAL_FOR_STAGE2", "measurement_grade": "STRUCTURAL_ONLY", "verified_savings_available": False, "raw_secret_stored": False, "provider": provider, "model": model, "credential_name": contract.get("credential_name")}
    if not preflight.get("execution_confirmation_valid", False):
        return {"status": "BLOCKED_UNTIL_CONFIRMED", "provider_authenticated": False, "verdict": "PROVIDER_PAID_EXECUTION_APPROVED_REQUIRED", "measurement_grade": "STRUCTURAL_ONLY", "verified_savings_available": False, "raw_secret_stored": False, "provider": provider, "model": model}
    return {"status": "BLOCKED", "provider_authenticated": False, "verdict": "PROVIDER_RESULT_MISSING", "measurement_grade": "UNKNOWN", "verified_savings_available": False, "raw_secret_stored": False, "provider": provider, "model": model}


def _diagnosis(static_report: dict[str, Any], binding: dict[str, Any] | None, provider: dict[str, Any]) -> list[dict[str, Any]]:
    aggregate = ((binding or {}).get("static_precheck") or {}).get("aggregate_counts") or {}
    findings = static_report.get("findings") or []
    if not aggregate:
        aggregate = {str(item.get("rule", "unknown")): int(item.get("signal_count", 0) or 0) for item in findings}
    result: list[dict[str, Any]] = []
    for key, (title, recommendation, impact, estimate) in RULE_TEXT.items():
        aliases = {key, key.lower(), key.replace("_", "-").lower(), key.lower() + "_signals"}
        if key == "MODEL_CALL":
            aliases.update({"model_call_signals", "model_calls"})
        elif key == "RETRY_LOOP":
            aliases.update({"retry_signals", "retry_loop"})
        elif key == "CACHE_SIGNAL":
            aliases.update({"cache_signals", "cache"})
        elif key == "TOKEN_LIMIT":
            aliases.update({"token_signals", "token_limit_signals", "context_signals"})
        count = sum(int(value or 0) for name, value in aggregate.items() if str(name) in aliases or str(name).upper() == key)
        if count <= 0:
            continue
        result.append({"priority": len(result) + 1, "problem": title, "evidence": {"signal_count": count, "source": "TARGET_REPOSITORY_CHECKOUT", "not_billing": True}, "why_cost_grows": "반복 호출·재시도·불필요한 문맥이 실제 사용량을 늘릴 수 있습니다.", "improvement": recommendation, "expected_impact": impact, "estimated_savings_range": estimate, "verification_level": "L1_STRUCTURAL_DIAGNOSIS", "provider_detected": provider.get("provider") or "UNKNOWN"})
    if not result:
        result.append({"priority": 1, "problem": "명확한 비용 구조 후보 없음", "evidence": {"source": "TARGET_REPOSITORY_CHECKOUT", "signal_count": 0, "not_billing": True}, "why_cost_grows": "현재 범위에서 LLM 비용 신호가 확인되지 않았습니다.", "improvement": "실제 사용량 또는 안전한 workload descriptor가 있으면 동일 조건 측정을 추가하세요.", "expected_impact": "LOW", "estimated_savings_range": "UNKNOWN", "verification_level": "L1_STRUCTURAL_DIAGNOSIS", "provider_detected": provider.get("provider") or "UNKNOWN"})
    return result[:5]


def build_report(static_report: dict[str, Any], acceptance: dict[str, Any], optimizer_dir: Path, preflight: dict[str, Any], provider_result: dict[str, Any] | None, active_project: str | None = None, target_binding: dict[str, Any] | None = None, target_precheck: dict[str, Any] | None = None) -> dict[str, Any]:
    binding = target_binding or target_precheck
    if binding is None and active_project:
        binding = {"target_repository": active_project, "target_fingerprint": None, "provider_contract": {}, "static_precheck": {"aggregate_counts": {}}, "workload": {"ready": False, "reason": "TARGET_BINDING_EVIDENCE_REQUIRED"}}
    fixture = fixture_reference(optimizer_dir, acceptance)
    provider = provider_gate(preflight, provider_result, binding)
    actual_available = bool(provider.get("verified_savings_available"))
    aggregate = ((binding or {}).get("static_precheck") or {}).get("aggregate_counts") or {}
    detected = provider.get("provider") or _contract(binding).get("provider")
    workload = (binding or {}).get("workload") or {}
    deterministic = bool(workload.get("ready"))
    priced = bool(preflight.get("pricing_status") in {"PROVIDER_PUBLISHED", "CUSTOMER_CONTRACT", "EXPLICIT_ZERO"})
    if actual_available:
        grade, verdict = "L5_VERIFIED_SAVINGS", "VERIFIED_SAVINGS"
    elif priced and deterministic:
        grade, verdict = "L3_ESTIMATED_COST_SAVINGS", "ESTIMATED_SAVINGS"
    else:
        grade, verdict = "L1_STRUCTURAL_DIAGNOSIS", "STRUCTURAL_DIAGNOSIS"
    reported = provider_result.get("stages") if actual_available and provider_result else {phase: None for phase in PHASES}
    diagnosis = _diagnosis(static_report, binding, provider)
    summary = {
        "what_wasted": diagnosis,
        "what_changed": ["Stage 1 정적 precheck 결과를 Stage 2 진단 후보로 확장", "target checkout의 runner-local shadow에서만 측정 후보를 구성", "정적·fixture 수치는 실제 청구 절감으로 승격하지 않음"],
        "before_cost": "UNKNOWN" if not actual_available else provider_result.get("stages", {}).get("raw", {}).get("cost_usd"),
        "after_cost": "UNKNOWN" if not actual_available else provider_result.get("stages", {}).get("engine_costdoctor", {}).get("cost_usd"),
        "savings_rate": "UNKNOWN" if not actual_available else provider_result.get("savings", {}).get("total_fraction"),
        "tokens_usage": "PROVIDER_REPORTED_USAGE" if actual_available else "UNKNOWN; deterministic/structural evidence only",
        "quality": "NON_REGRESSION_VERIFIED" if actual_available else "PENDING_PROVIDER_OR_LOCAL_DESCRIPTOR",
        "verification_cost": "UNKNOWN" if not actual_available else provider_result.get("validation_overhead_usd", "UNKNOWN"),
        "net_saving": "UNKNOWN" if not actual_available else provider_result.get("net_saving_usd", "UNKNOWN"),
    }
    return {
        "schema": "costdoctor.public-verified-savings.universal-stage2.v3",
        "report_schema_version": "3.0.0",
        "verdict": verdict,
        "trust_level": grade,
        "target_binding": {"repository": (binding or {}).get("target_repository"), "ref": (binding or {}).get("target_ref"), "commit": (binding or {}).get("target_commit"), "fingerprint": (binding or {}).get("target_fingerprint"), "provider_contract": _contract(binding), "workload": {key: value for key, value in workload.items() if key not in {"prompt", "items"}}, "bound": bool(binding and binding.get("target_fingerprint"))},
        "static_precheck": {"status": "PASS" if binding else "UNKNOWN", "signal_counts": aggregate, "source": "TARGET_REPOSITORY_CHECKOUT" if binding else "UNBOUND", "not_billing_or_savings": True},
        "stage2_diagnosis": {"status": "PASS", "evidence_level": grade, "provider_detected": detected, "provider_candidates": ((binding or {}).get("provider_detection") or {}).get("provider_candidates", []), "findings": diagnosis, "secretless_continuation": True},
        "fixture_reference": fixture,
        "provider": provider,
        "reported_stages": reported,
        "reported_stage_reason": "PROVIDER_AUTHENTICATED_TARGET_RECEIPT" if actual_available else "Provider usage is optional; structural/estimated Stage 2 remains available and fixture claims are excluded.",
        "quality": {"provider_before": provider_result.get("stages", {}).get("raw", {}).get("quality") if provider_result else None, "provider_after": provider_result.get("stages", {}).get("engine_costdoctor", {}).get("quality") if provider_result else None, "fixture_quality_non_regression": all(row.get("quality", {}).get("failed_phases", []) == [] for row in acceptance.get("workloads", [])), "target_workload_ready": deterministic, "verdict": "PASS" if actual_available else "NOT_MEASURED_PROVIDER"},
        "validation_overhead": {"optimizer_monetary_cost_usd": "0.000000000", "provider_validation_cost_usd": None if not actual_available else provider_result.get("validation_overhead_usd"), "rollback_reapply_included": bool(provider_result and provider_result.get("rollback", {}).get("actual_status") == "PASS"), "net_saving_usd": None if not actual_available else summary["net_saving"], "break_even": "UNKNOWN" if not actual_available else provider_result.get("break_even", "UNKNOWN")},
        "user_summary": summary,
        "false_pass_guards": {"target_binding_required": True, "static_not_promoted": True, "byte_proxy_not_provider_usage": True, "unknown_price_blocked": True, "different_workload_blocked": True, "quality_drop_blocks": True, "spend_cap_enforced": True, "raw_secret_output": False, "raw_target_source_output": False, "shadow_repo_write": False, "fixture_not_target": True, "provider_is_registry_selected": True, "secret_optional_for_stage2": True},
        "user_action_queue": [],
    }


def render_markdown(report: dict[str, Any]) -> str:
    target = report["target_binding"]
    summary = report["user_summary"]
    lines = ["# CostDoctor 결과", "", f"종합판정: **{report['verdict']}**", f"Evidence 등급: **{report['trust_level']}**", f"대상 결속: `{target.get('repository') or 'UNKNOWN'}` / `{target.get('commit') or 'UNKNOWN'}`", "", "## 가장 큰 비용 문제", ""]
    for item in summary["what_wasted"]:
        lines.extend([f"### {item['priority']}. {item['problem']}", f"- 발견 근거: {item['evidence'].get('signal_count', 0)}개 정적 신호 ({item['verification_level']})", f"- 왜 비용이 드는지: {item['why_cost_grows']}", f"- 개선 방법: {item['improvement']}", f"- 예상 효과: {item['expected_impact']} / {item['estimated_savings_range']}", ""])
    lines.extend(["## 비용·토큰", f"- Before 비용: **{summary['before_cost']}**", f"- After 비용: **{summary['after_cost']}**", f"- 절감률: **{summary['savings_rate']}**", f"- 사용량: **{summary['tokens_usage']}**", "", "## 품질·안전", f"- 품질: **{summary['quality']}**", "- 고객 저장소 자동 수정: **없음**", "- 원문 소스·Secret 외부 전송/저장: **없음**", "", "Provider Secret이 없어도 이 Stage 2 구조 진단은 완료되며, 실제 usage가 연결될 때만 VERIFIED_SAVINGS로 승격됩니다.", ""])
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
