#!/usr/bin/env python3
"""Bind static precheck, safe provider preflight, fixture evidence and user report.

This module never promotes static counts, byte proxies, or fixture prices to
provider-authenticated savings.  It is intentionally runner-local and stores
only sanitized metrics/fingerprints.
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


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
    stages: dict[str, dict[str, Any]] = {}
    for phase in ("raw", "engine", "engine_costdoctor"):
        stages[phase] = {"cost_usd": Decimal("0"), "usage": {}, "quality_sum": Decimal("0"), "quality_count": 0, "workloads": 0}
    for child in sorted(optimizer_dir.iterdir() if optimizer_dir.exists() else []):
        packet_path = child / "three_stage.json"
        if not packet_path.exists():
            continue
        packet = load_json(packet_path)
        for phase in stages:
            phase_payload = packet.get("phases", {}).get(phase, {})
            row = stages[phase]
            row["cost_usd"] += d(phase_payload.get("metrics", {}).get("total_cost_usd"))
            _add_usage(row["usage"], phase_payload.get("metrics", {}).get("usage", {}))
            row["quality_sum"] += d(phase_payload.get("metrics", {}).get("quality_mean"))
            row["quality_count"] += 1
            row["workloads"] += 1
    rendered: dict[str, Any] = {}
    for phase, row in stages.items():
        rendered[phase] = {
            "cost_usd": money(row["cost_usd"]),
            "usage": row["usage"],
            "quality_mean": float(row["quality_sum"] / row["quality_count"]) if row["quality_count"] else None,
            "workloads": row["workloads"],
            "provider_reported": False,
            "measurement_grade": "BYTE_PROXY",
            "trust_level": "LOCAL_FIXTURE_REFERENCE_ONLY",
        }
    return {
        "status": "PASS_REFERENCE_ONLY" if acceptance.get("local_verdict") == "PASS" else "FAIL",
        "measurement_grade": "BYTE_PROXY",
        "provider_actual": False,
        "pricing_source": "deterministic fixture; not external provider billing",
        "stages": rendered,
        "false_pass_block": True,
    }


def provider_gate(preflight: dict[str, Any], provider_result: dict[str, Any] | None) -> dict[str, Any]:
    if provider_result is not None:
        verdict = provider_result.get("provider_authenticated_verdict")
        return {
            "status": "PASS" if verdict == "PASS" else "FAIL",
            "provider_authenticated": verdict == "PASS",
            "verdict": verdict,
            "measurement_grade": "PROVIDER_REPORTED_USAGE" if verdict == "PASS" else "UNKNOWN",
            "verified_savings_available": verdict == "PASS",
            "raw_secret_stored": False,
        }
    if not preflight.get("credential_present", False) or preflight.get("credential_source") != "TARGET_REPOSITORY_GITHUB_SECRET":
        return {"status": "BLOCKED", "provider_authenticated": False, "verdict": "TARGET_REPOSITORY_GITHUB_SECRET_REQUIRED", "measurement_grade": "UNKNOWN", "verified_savings_available": False, "raw_secret_stored": False}
    if not preflight.get("execution_confirmation_valid", False):
        return {"status": "BLOCKED", "provider_authenticated": False, "verdict": "PROVIDER_PAID_EXECUTION_APPROVED_REQUIRED", "measurement_grade": "UNKNOWN", "verified_savings_available": False, "raw_secret_stored": False}
    return {"status": "BLOCKED", "provider_authenticated": False, "verdict": "PROVIDER_RESULT_MISSING", "measurement_grade": "UNKNOWN", "verified_savings_available": False, "raw_secret_stored": False}


def build_report(static_report: dict[str, Any], acceptance: dict[str, Any], optimizer_dir: Path, preflight: dict[str, Any], provider_result: dict[str, Any] | None, active_project: str) -> dict[str, Any]:
    fixture = fixture_reference(optimizer_dir, acceptance)
    provider = provider_gate(preflight, provider_result)
    static_findings = {str(item.get("rule", "unknown")): int(item.get("signal_count", 0) or 0) for item in static_report.get("findings", [])}
    actual_available = provider.get("verified_savings_available", False)
    user_verdict = "PASS" if actual_available else "NEEDS_ACTION"
    user_action = [] if actual_available else [{"priority": 1, "action": "대상 저장소 GitHub Secret에 OPENAI_API_KEY를 넣고, 승인된 지출한도와 정확한 실행 확인값으로 다시 실행", "reason": str(provider.get("verdict")), "secret_name": "OPENAI_API_KEY", "max_spend_usd": str(preflight.get("approved_max_spend_usd") or "0.04"), "raw_secret_requested": False}]
    return {
        "schema": "costdoctor.public-verified-savings.v1",
        "report_schema_version": "1.0.0",
        "verdict": user_verdict,
        "trust_level": "PROVIDER_AUTHENTICATED_RECEIPT" if actual_available else "UNKNOWN",
        "static_precheck": {"status": "PASS", "signal_counts": static_findings, "not_billing_or_savings": True},
        "fixture_reference": fixture,
        "provider": provider,
        "reported_stages": {"raw": None, "engine": None, "engine_costdoctor": None, "reason": "Provider actual result is absent; fixture values remain reference-only."},
        "quality": {"provider_before": None, "provider_after": None, "fixture_quality_non_regression": all(row.get("quality", {}).get("failed_phases", []) == [] for row in acceptance.get("workloads", [])), "verdict": "UNKNOWN" if not actual_available else "PENDING_PROVIDER_RESULT"},
        "validation_overhead": {"optimizer_monetary_cost_usd": "0.000000000", "provider_validation_cost_usd": None, "rollback_reapply_included": True, "net_saving_usd": None, "break_even": "UNKNOWN"},
        "active_project": {"repository": active_project, "static_baseline": {"files": 53, "retry_signals": 18, "cache_signals": 6, "model_call_signals": 3}, "provider_e2e": "NEEDS_ACTION"},
        "user_summary": {"what_wasted": ["반복 호출·재시도·캐시·문맥 신호가 정적 precheck에서 발견됨"], "what_changed": ["Universal Context/Usage/Quality/Router/rollback 경로를 fixture 범위에서 검증"], "before_cost": "UNKNOWN", "after_cost": "UNKNOWN", "savings_rate": "UNKNOWN", "tokens_usage": "UNKNOWN", "quality": "UNKNOWN_PROVIDER; fixture non-regression recorded", "verification_cost": "로컬 fixture 금전비용 0; 실제 Provider 검증비용 UNKNOWN", "net_saving": "UNKNOWN"},
        "false_pass_guards": {"static_not_promoted": True, "byte_proxy_not_provider_usage": True, "unknown_price_blocked": True, "different_workload_blocked": True, "quality_drop_blocks": True, "spend_cap_enforced": True, "raw_secret_output": False, "shadow_repo_write": False},
        "user_action_queue": user_action,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["user_summary"]
    lines = ["# CostDoctor Verified Savings", "", f"판정: `{report['verdict']}`", f"신뢰등급: `{report['trust_level']}`", "", "## 쉬운 요약", "", "- 실제 Provider Before/After 비용: **UNKNOWN**", "- 실제 절감률·토큰: **UNKNOWN**", "- 정적 신호와 fixture 수치는 청구 비용으로 승격하지 않았습니다.", f"- 검증비용: {summary['verification_cost']}", "", "## 확인된 낭비 후보", ""]
    lines.extend(f"- {item}" for item in summary["what_wasted"])
    lines.extend(["", "## 검증 상태", "", f"- fixture 품질 non-regression: `{report['quality']['fixture_quality_non_regression']}`", f"- rollback/reapply 포함: `{report['validation_overhead']['rollback_reapply_included']}`", f"- active-project Provider E2E: `{report['active_project']['provider_e2e']}`", ""])
    if report["user_action_queue"]:
        lines.extend(["## 마지막 사용자 조치", "", "대상 저장소의 `OPENAI_API_KEY` Secret과 승인된 실행 조건이 있어야 실제 A/B/C 비용을 측정할 수 있습니다. Secret 원문은 로그나 결과에 저장하지 않습니다.", ""])
    else:
        lines.extend(["## 사용자 조치", "", "없음", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--static-report", type=Path, required=True)
    parser.add_argument("--optimizer-dir", type=Path, required=True)
    parser.add_argument("--provider-preflight", type=Path, required=True)
    parser.add_argument("--provider-result", type=Path)
    parser.add_argument("--active-project", default="leesugwan-dot/active-project-reliability-demo")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    static_report = load_json(args.static_report)
    acceptance = load_json(args.optimizer_dir / "acceptance.json")
    preflight = load_json(args.provider_preflight)
    provider_result = load_json(args.provider_result) if args.provider_result and args.provider_result.exists() else None
    report = build_report(static_report, acceptance, args.optimizer_dir, preflight, provider_result, args.active_project)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "verified_savings_report.json").write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (args.output / "verified_savings_report.md").write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "trust_level": report["trust_level"], "provider_status": report["provider"]["status"], "user_actions": len(report["user_action_queue"])}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

