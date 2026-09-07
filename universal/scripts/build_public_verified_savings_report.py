#!/usr/bin/env python3
"""Build a sanitized, target-bound verified-savings report."""
from __future__ import annotations

import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


EXPECTED = {"provider": "upstage", "model": "solar-pro3", "credential_name": "UPSTAGE_API_KEY", "base_url": "https://api.upstage.ai/v1"}


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
    stages: dict[str, dict[str, Any]] = {phase: {"cost_usd": Decimal("0"), "usage": {}, "quality_sum": Decimal("0"), "quality_count": 0, "workloads": 0} for phase in ("raw", "engine", "engine_costdoctor")}
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
    return {"status": "PASS_REFERENCE_ONLY" if acceptance.get("local_verdict") == "PASS" else "FAIL", "measurement_grade": "BYTE_PROXY", "provider_actual": False, "pricing_source": "deterministic fixture; not external provider billing", "stages": rendered, "false_pass_block": True, "claim_scope": "ENGINE_SELF_TEST/PROVIDER_REFERENCE"}


def target_contract(binding: dict[str, Any] | None) -> dict[str, Any]:
    contract = dict((binding or {}).get("provider_contract") or {})
    return {key: contract.get(key) for key in EXPECTED}


def provider_gate(preflight: dict[str, Any], provider_result: dict[str, Any] | None, binding: dict[str, Any] | None) -> dict[str, Any]:
    if target_contract(binding) != EXPECTED:
        return {"status": "BLOCKED", "provider_authenticated": False, "verdict": "TARGET_PROVIDER_CONTRACT_MISMATCH", "measurement_grade": "UNKNOWN", "verified_savings_available": False, "raw_secret_stored": False}
    if provider_result is not None:
        same_binding = provider_result.get("target_binding_fingerprint") == (binding or {}).get("target_fingerprint") and provider_result.get("target_repository") == (binding or {}).get("target_repository") and provider_result.get("target_commit") == (binding or {}).get("target_commit") and provider_result.get("workload_fingerprint") == ((binding or {}).get("workload") or {}).get("fingerprint") and provider_result.get("provider") == EXPECTED["provider"] and provider_result.get("model") == EXPECTED["model"]
        authenticated = provider_result.get("provider_authenticated_verdict") == "PASS" and provider_result.get("pricing_status") == "PROVIDER_PUBLISHED" and same_binding
        return {"status": "PASS" if authenticated else "BLOCKED", "provider_authenticated": authenticated, "verdict": "PASS" if authenticated else ("TARGET_BINDING_MISMATCH" if not same_binding else "UNKNOWN_PRICE_OR_PROVIDER_VERIFICATION"), "measurement_grade": provider_result.get("measurement_grade", "UNKNOWN"), "verified_savings_available": authenticated, "raw_secret_stored": False, "target_binding_match": same_binding}
    if not preflight.get("credential_present", False) or preflight.get("credential_source") != "TARGET_REPOSITORY_GITHUB_SECRET":
        return {"status": "BLOCKED", "provider_authenticated": False, "verdict": "TARGET_REPOSITORY_GITHUB_SECRET_REQUIRED", "measurement_grade": "UNKNOWN", "verified_savings_available": False, "raw_secret_stored": False}
    if not preflight.get("execution_confirmation_valid", False):
        return {"status": "BLOCKED", "provider_authenticated": False, "verdict": "PROVIDER_PAID_EXECUTION_APPROVED_REQUIRED", "measurement_grade": "UNKNOWN", "verified_savings_available": False, "raw_secret_stored": False}
    return {"status": "BLOCKED", "provider_authenticated": False, "verdict": "PROVIDER_RESULT_MISSING", "measurement_grade": "UNKNOWN", "verified_savings_available": False, "raw_secret_stored": False}


def _binding_from_legacy(active_project: str | None) -> dict[str, Any] | None:
    if not active_project:
        return None
    return {"target_repository": active_project, "target_fingerprint": None, "provider_contract": dict(EXPECTED), "static_precheck": {"aggregate_counts": {}}, "workload": {"ready": False, "reason": "TARGET_BINDING_EVIDENCE_REQUIRED"}}


def build_report(static_report: dict[str, Any], acceptance: dict[str, Any], optimizer_dir: Path, preflight: dict[str, Any], provider_result: dict[str, Any] | None, active_project: str | None = None, target_binding: dict[str, Any] | None = None, target_precheck: dict[str, Any] | None = None) -> dict[str, Any]:
    binding = target_binding or target_precheck or _binding_from_legacy(active_project)
    fixture = fixture_reference(optimizer_dir, acceptance)
    provider = provider_gate(preflight, provider_result, binding)
    static_findings = {str(item.get("rule", "unknown")): int(item.get("signal_count", 0) or 0) for item in static_report.get("findings", [])}
    aggregate = ((binding or {}).get("static_precheck") or {}).get("aggregate_counts") or {}
    actual_available = provider.get("verified_savings_available", False)
    secret_action = [{"priority": 1, "action": "대상 저장소에 UPSTAGE_API_KEY Secret을 등록하고 승인된 지출한도로 target-bound workflow를 다시 실행", "reason": str(provider.get("verdict")), "secret_name": EXPECTED["credential_name"], "target_repository": (binding or {}).get("target_repository"), "max_spend_usd": str(preflight.get("approved_max_spend_usd") or "0.04"), "raw_secret_requested": False}] if provider.get("verdict") == "TARGET_REPOSITORY_GITHUB_SECRET_REQUIRED" else []
    workload_ready = bool(((binding or {}).get("workload") or {}).get("ready"))
    reported = provider_result.get("stages") if actual_available and provider_result else {"raw": None, "engine": None, "engine_costdoctor": None}
    return {"schema": "costdoctor.public-verified-savings.target-bound.v2", "report_schema_version": "2.0.0", "verdict": "PASS" if actual_available else "NEEDS_ACTION", "trust_level": "PROVIDER_AUTHENTICATED_RECEIPT" if actual_available else "UNKNOWN", "target_binding": {"repository": (binding or {}).get("target_repository"), "ref": (binding or {}).get("target_ref"), "commit": (binding or {}).get("target_commit"), "fingerprint": (binding or {}).get("target_fingerprint"), "provider_contract": target_contract(binding), "workload": {key: value for key, value in (((binding or {}).get("workload") or {}).items()) if key not in {"prompt", "items"}}, "bound": bool(binding and (binding or {}).get("target_fingerprint"))}, "static_precheck": {"status": "PASS" if binding else "UNKNOWN", "signal_counts": aggregate or static_findings, "source": "TARGET_REPOSITORY_CHECKOUT" if binding else "UNBOUND", "not_billing_or_savings": True}, "fixture_reference": fixture, "provider": provider, "reported_stages": reported, "reported_stage_reason": "Target provider receipt is absent, mismatched, unpriced, or not authenticated; reference fixtures are excluded." if not actual_available else "PROVIDER_AUTHENTICATED_TARGET_RECEIPT", "quality": {"provider_before": provider_result.get("stages", {}).get("raw", {}).get("quality") if provider_result else None, "provider_after": provider_result.get("stages", {}).get("engine_costdoctor", {}).get("quality") if provider_result else None, "fixture_quality_non_regression": all(row.get("quality", {}).get("failed_phases", []) == [] for row in acceptance.get("workloads", [])), "target_workload_ready": workload_ready, "verdict": "PASS" if actual_available else "UNKNOWN"}, "validation_overhead": {"optimizer_monetary_cost_usd": "0.000000000", "provider_validation_cost_usd": None, "rollback_reapply_included": bool(provider_result and provider_result.get("rollback", {}).get("actual_status") == "PASS"), "net_saving_usd": None, "break_even": "UNKNOWN"}, "user_summary": {"what_wasted": [f"{name}: {value}개 정적 신호" for name, value in sorted(aggregate.items()) if name != "files" and int(value or 0) > 0] or ["대상 저장소 정적 신호는 target checkout에서 계산되며, 현재 보고서에 승격된 청구 비용은 없습니다."], "what_changed": ["target checkout의 runner-local shadow 경로에서만 A/B/C를 시도", "정적·fixture 수치는 target savings에서 분리"], "before_cost": "UNKNOWN", "after_cost": "UNKNOWN", "savings_rate": "UNKNOWN", "tokens_usage": "UNKNOWN", "quality": "UNKNOWN_PROVIDER; target-bound evidence required", "verification_cost": "실제 Provider 검증비용 UNKNOWN", "net_saving": "UNKNOWN"}, "false_pass_guards": {"target_binding_required": True, "static_not_promoted": True, "byte_proxy_not_provider_usage": True, "unknown_price_blocked": True, "different_workload_blocked": True, "quality_drop_blocks": True, "spend_cap_enforced": True, "raw_secret_output": False, "raw_target_source_output": False, "shadow_repo_write": False, "openai_fixture_not_target": True}, "user_action_queue": secret_action}


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["user_summary"]
    target = report["target_binding"]
    lines = ["# CostDoctor Verified Savings", "", f"판정: `{report['verdict']}`", f"신뢰등급: `{report['trust_level']}`", f"대상 결속: `{target.get('repository') or 'UNKNOWN'}` / `{target.get('commit') or 'UNKNOWN'}`", "", "## 쉬운 요약", "", "- 실제 Provider Before/After 비용: **UNKNOWN**", "- 실제 절감률·토큰: **UNKNOWN**", "- 정적 신호와 OpenAI fixture는 대상 저장소 절감으로 승격하지 않았습니다.", f"- 검증비용: {summary['verification_cost']}", "", "## 확인된 낭비 후보", ""]
    lines.extend(f"- {item}" for item in summary["what_wasted"])
    lines.extend(["", "## 검증 상태", "", f"- target workload 준비: `{report['quality']['target_workload_ready']}`", f"- rollback/reapply 포함: `{report['validation_overhead']['rollback_reapply_included']}`", f"- Provider 상태: `{report['provider']['verdict']}`", ""])
    if report["user_action_queue"]:
        lines.extend(["## 마지막 사용자 조치", "", "대상 저장소에 `UPSTAGE_API_KEY` Secret을 등록한 뒤 승인된 지출한도로 target-bound workflow를 다시 실행하세요. Secret 원문은 로그나 결과에 저장하지 않습니다.", ""])
    else:
        lines.extend(["## 사용자 조치", "", "없음", ""])
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
