from __future__ import annotations

from typing import Any


LEVELS = {"VERIFIED", "MEASURED", "STATIC_SIGNAL", "ESTIMATED", "UNKNOWN", "BLOCKED"}


def render_report(packet: dict[str, Any], validation: dict[str, Any], language: str = "ko") -> str:
    verified = validation.get("verdict") == "PASS"
    level = "VERIFIED" if verified else "BLOCKED" if validation.get("verdict") in {"BLOCKED", "FAIL"} else "UNKNOWN"
    if level not in LEVELS:
        level = "UNKNOWN"
    before = packet["before"]["metrics"]
    after = packet["after"]["metrics"]
    top = packet.get("detectors", [])[:3]
    if language == "en":
        lines = [
            f"# CostDoctor result — {packet['workload_id']}",
            f"Result: **{level}**",
            f"Why: independent validator `{validation.get('verdict')}`; quality `{packet['quality']['verdict']}`.",
            f"Measured: before ${before.get('total_cost_usd')} → after ${after.get('total_cost_usd')} for this deterministic fixture scope.",
            "Estimated/static: detector findings are candidates until benchmarked.",
            f"Verified savings: {validation.get('verified_savings_usd') if verified else 'UNKNOWN'} USD (fixture scope only).",
            f"Quality: {packet['quality'].get('before_mean')} → {packet['quality'].get('after_mean')}.",
            f"Rollback: {packet['rollback'].get('actual_status')}.",
            "Top actions:",
            *[f"- {item['detector']}: {item['recommendation']}" for item in top],
            "Next: validate the same route using customer-owned usage Evidence before any production claim.",
        ]
    else:
        lines = [
            f"# CostDoctor 결과 — {packet['workload_id']}",
            f"결과: **{level}**",
            f"이유: 독립검증 `{validation.get('verdict')}`, 품질검사 `{packet['quality']['verdict']}`입니다.",
            f"실제 측정: 이 결정형 fixture 범위에서 ${before.get('total_cost_usd')} → ${after.get('total_cost_usd')}입니다.",
            "추정/정적 신호: detector 결과는 동일조건 benchmark 전에는 개선 후보일 뿐입니다.",
            f"검증 절감액: {validation.get('verified_savings_usd') if verified else 'UNKNOWN'} USD (fixture 범위 한정).",
            f"품질 변화: {packet['quality'].get('before_mean')} → {packet['quality'].get('after_mean')}.",
            f"rollback: {packet['rollback'].get('actual_status')}.",
            "효과가 큰 다음 조치:",
            *[f"- {item['detector']}: {item['recommendation']}" for item in top],
            "다음 행동: 운영 환경 절감 주장을 하기 전에 고객 소유 사용량 Evidence로 같은 경로를 검증하세요.",
        ]
    return "\n\n".join(lines) + "\n"
