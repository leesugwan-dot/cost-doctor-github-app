from __future__ import annotations

from decimal import Decimal
from html import escape
from typing import Any

from .canonical import decimal_text


TRUST_LEVELS = {
    "VERIFIED",
    "MEASURED",
    "ESTIMATED",
    "BILLING_CONFIRMED",
    "STATIC_SIGNAL",
    "UNKNOWN",
    "BLOCKED",
}
APPLICATION_STATES = {
    "APPLIED_AND_VERIFIED",
    "PROPOSED_ONLY",
    "APPLY_FAILED",
    "ROLLED_BACK",
    "NOT_APPLICABLE",
}

DETECTOR_LABEL_KO = {
    "duplicate_call": "같은 작업을 여러 번 호출함",
    "identical_input_repeat": "같은 입력을 다시 처리함",
    "repeated_prefix": "같은 앞부분 문맥을 반복 전송함",
    "oversized_context": "필요 이상으로 긴 문맥을 전송함",
    "full_history_reinjection": "전체 대화 이력을 반복 전송함",
    "duplicate_retrieval": "같은 자료를 중복 검색함",
    "low_relevance_rag": "관련성이 낮은 자료가 많이 포함됨",
    "excessive_output_limit": "출력 한도가 실제 사용량보다 큼",
    "inefficient_chunk_overlap": "문서 조각이 과도하게 겹침",
    "inefficient_chunk_size": "문서 조각 크기가 비효율적임",
    "summary_missing": "긴 대화 요약을 사용하지 않음",
    "excessive_retry": "재시도가 너무 많음",
    "same_error_retry": "같은 오류를 반복 재시도함",
    "retry_backoff_invalid": "재시도 간격이 적절하지 않음",
    "full_reexecution_after_failure": "실패 뒤 전체 작업을 다시 실행함",
    "timeout_duplicate": "시간초과로 중복 실행될 수 있음",
    "idempotency_missing": "중복 실행 방지 키가 없음",
    "cache_missing": "재사용 가능한 결과를 캐시하지 않음",
    "low_cache_hit_rate": "캐시 적중률이 낮음",
    "cache_ttl_mismatch": "캐시 유지 시간이 재사용 패턴과 맞지 않음",
    "cache_scope_unsafe": "캐시의 사용자·권한 구분이 안전하지 않음",
    "cache_cost_exceeds_saving": "캐시 비용이 절감액보다 큼",
    "overqualified_model": "작업보다 과한 모델을 사용함",
    "simple_task_expensive_model": "간단한 작업에 비싼 모델을 사용함",
    "excessive_reasoning": "간단한 작업에 추론량이 과도함",
    "fallback_chain_excess": "대체 모델 연결이 너무 김",
    "model_switch_rework": "모델 전환으로 재작업이 발생함",
    "repeated_tool_loop": "같은 도구를 반복 호출함",
    "planner_reviewer_duplication": "계획·검토 호출이 중복됨",
    "multi_agent_duplicate": "여러 작업자가 같은 일을 중복 수행함",
    "repeated_fetch": "같은 외부 자료를 반복 조회함",
    "large_tool_output_reinjection": "큰 도구 출력을 반복 전송함",
    "model_used_for_local_compute": "로컬 계산으로 가능한 일을 모델이 처리함",
    "serial_parallelizable_calls": "독립 작업을 불필요하게 순차 실행함",
    "batch_opportunity": "묶음 처리 가능한 요청을 개별 실행함",
    "concurrency_retry_amplification": "동시 실행 때문에 재시도가 늘어남",
    "queue_duplicate_execution": "대기열 작업이 중복 실행됨",
    "model_occupied_while_waiting": "대기 중에도 모델 작업을 점유함",
    "failure_cost_spike": "실패 때문에 완료당 비용이 증가함",
    "latency_spike": "일부 실행의 지연이 크게 증가함",
    "tool_rework_cost": "도구 결과 재작업 비용이 발생함",
}

ACTION_KO = {
    "duplicate_call": "같은 작업의 중복 호출을 합치세요.",
    "identical_input_repeat": "사용자·권한 범위가 같은 결과만 안전하게 재사용하세요.",
    "repeated_prefix": "반복되는 앞부분 문맥을 안전한 캐시나 짧은 요약으로 바꾸세요.",
    "oversized_context": "답에 영향을 주지 않는 문맥을 측정 후 제거하세요.",
    "full_history_reinjection": "전체 이력 대신 검증된 요약과 필요한 최근 대화만 보내세요.",
    "duplicate_retrieval": "문맥을 만들기 전에 중복 자료를 제거하세요.",
    "low_relevance_rag": "검색 관련성을 높이고 불필요한 자료를 줄이세요.",
    "excessive_output_limit": "품질을 지키는 범위에서 출력 한도를 낮추세요.",
    "inefficient_chunk_overlap": "문서 조각의 중복 구간을 줄여 다시 측정하세요.",
    "inefficient_chunk_size": "더 작은 문서 조각을 같은 품질 기준으로 비교하세요.",
    "summary_missing": "긴 대화를 제한된 요약으로 바꾸고 품질을 확인하세요.",
    "excessive_retry": "일시 오류만 횟수를 제한해 재시도하세요.",
    "same_error_retry": "고정 오류는 반복하지 말고 원인을 바로 표시하세요.",
    "retry_backoff_invalid": "일시 오류에만 제한된 지수형 재시도 간격을 사용하세요.",
    "full_reexecution_after_failure": "안전한 마지막 지점부터 다시 시작하세요.",
    "timeout_duplicate": "시간초과 실행에 중복 방지 영수증을 연결하세요.",
    "idempotency_missing": "사용자·권한 범위를 포함한 중복 방지 키를 추가하세요.",
    "cache_missing": "격리 범위를 지킨 캐시를 실제 측정으로 비교하세요.",
    "low_cache_hit_rate": "집계된 사용 증거로 캐시 키와 유지 시간을 조정하세요.",
    "cache_ttl_mismatch": "실제 재사용 간격에 맞춰 캐시 유지 시간을 조정하세요.",
    "cache_scope_unsafe": "사용자·권한·모델별로 캐시를 분리하세요.",
    "cache_cost_exceeds_saving": "절감보다 비싼 캐시 쓰기를 줄이거나 끄세요.",
    "overqualified_model": "품질을 통과하는 가장 저렴한 적합 모델을 비교하세요.",
    "simple_task_expensive_model": "간단한 작업은 같은 품질을 통과한 저비용 모델로 보내세요.",
    "excessive_reasoning": "같은 품질 기준으로 더 낮은 추론 수준을 시험하세요.",
    "fallback_chain_excess": "대체 모델 단계를 제한하고 품질을 다시 확인하세요.",
    "model_switch_rework": "모델 전환 이유를 기록하고 불필요한 전환을 줄이세요.",
    "repeated_tool_loop": "이미 확인한 도구 결과를 재사용하고 종료 조건을 두세요.",
    "planner_reviewer_duplication": "확정된 계획은 재사용하고 중요한 변경만 다시 검토하세요.",
    "multi_agent_duplicate": "각 작업의 담당 범위를 나누고 완료 증거를 재사용하세요.",
    "repeated_fetch": "변하지 않는 조회 결과를 출처와 함께 안전하게 재사용하세요.",
    "large_tool_output_reinjection": "큰 원문 대신 구조화된 요약과 정확한 참조를 전달하세요.",
    "model_used_for_local_compute": "결정형 로컬 계산으로 바꾸고 결과를 테스트하세요.",
    "serial_parallelizable_calls": "독립 호출을 제한된 범위에서 병렬 처리하세요.",
    "batch_opportunity": "지원되는 묶음 처리 방식을 같은 조건에서 비교하세요.",
    "concurrency_retry_amplification": "재시도까지 포함한 처리량이 좋아질 때까지 동시 실행을 낮추세요.",
    "queue_duplicate_execution": "대기열 완료 영수증으로 중복 실행을 막으세요.",
    "model_occupied_while_waiting": "외부 작업을 기다리는 동안 모델 점유를 해제하세요.",
    "failure_cost_spike": "가장 큰 실패 원인부터 고치고 성공 완료당 비용을 추적하세요.",
    "latency_spike": "지연 급증을 재시도·모델·대기열 증거와 함께 확인하세요.",
    "tool_rework_cost": "검증된 도구 결과를 작업에 묶어 안전하게 재사용하세요.",
}


def _savings_rate(before: str | None, saving: str | None) -> str | None:
    if before is None or saving is None or Decimal(str(before)) <= 0:
        return None
    return decimal_text(Decimal(str(saving)) * Decimal("100") / Decimal(str(before)))


def _application_state(
    packet: dict[str, Any], validation: dict[str, Any], requested: str | None
) -> str:
    if requested is not None:
        if requested not in APPLICATION_STATES:
            raise ValueError("APPLICATION_STATE_INVALID")
        return requested
    claim = packet.get("claim", {}).get("status")
    if validation.get("verdict") == "PASS" and packet.get("rollback", {}).get("actual_status") == "PASS":
        return "APPLIED_AND_VERIFIED"
    if claim == "NO_SAVINGS" and packet.get("rollback", {}).get("actual_status") == "PASS":
        return "ROLLED_BACK"
    if packet.get("quality", {}).get("verdict") == "FAIL":
        return "APPLY_FAILED"
    return "NOT_APPLICABLE"


def _trust_level(packet: dict[str, Any], validation: dict[str, Any]) -> str:
    claim = packet.get("claim", {})
    if validation.get("verdict") == "PASS" and validation.get("verified_savings_usd") is not None:
        return "VERIFIED"
    if claim.get("status") == "MEASURED_PENDING_INDEPENDENT_VALIDATION":
        return "MEASURED"
    if claim.get("status") == "UNKNOWN":
        return "UNKNOWN"
    if validation.get("verdict") in {"FAIL", "BLOCKED"}:
        return "BLOCKED"
    if packet.get("detectors"):
        return "STATIC_SIGNAL"
    return "UNKNOWN"


def _user_verdict(packet: dict[str, Any], validation: dict[str, Any]) -> str:
    claim = packet.get("claim", {}).get("status")
    quality = packet.get("quality", {}).get("verdict")
    if claim == "NO_SAVINGS":
        return "NO_SAVINGS"
    if claim in {"UNKNOWN", "BLOCKED", "INCONCLUSIVE"}:
        return "BLOCKED"
    if quality == "FAIL":
        return "FAIL"
    if quality == "NEEDS_EVIDENCE" or validation.get("verdict") == "NEEDS_EVIDENCE":
        return "NEEDS_EVIDENCE"
    if validation.get("verdict") == "PASS" and validation.get("verified_savings_usd") is not None:
        return "PASS"
    if validation.get("verdict") == "FAIL":
        return "FAIL"
    return "BLOCKED"


def build_user_report(
    packet: dict[str, Any],
    validation: dict[str, Any],
    application_state: str | None = None,
) -> dict[str, Any]:
    before = packet.get("before", {}).get("metrics", {})
    after = packet.get("after", {}).get("metrics", {})
    quality = packet.get("quality", {})
    verified = validation.get("verified_savings_usd") if validation.get("verdict") == "PASS" else None
    verdict = _user_verdict(packet, validation)
    trust = _trust_level(packet, validation)
    state = _application_state(packet, validation, application_state)
    facts = {
        "verdict": verdict,
        "trust_level": trust,
        "application_state": state,
        "before_cost_usd": before.get("total_cost_usd"),
        "after_cost_usd": after.get("total_cost_usd"),
        "verified_savings_usd": verified,
        "savings_rate_percent": _savings_rate(before.get("total_cost_usd"), verified),
        "quality_before": quality.get("before_mean"),
        "quality_after": quality.get("after_mean"),
        "quality_verdict": quality.get("verdict", "NEEDS_EVIDENCE"),
        "rollback_status": packet.get("rollback", {}).get("actual_status", "UNKNOWN"),
        "pricing_status_before": before.get("pricing_status", "UNKNOWN"),
        "pricing_status_after": after.get("pricing_status", "UNKNOWN"),
        "independent_validation": validation.get("verdict", "NEEDS_EVIDENCE"),
    }
    findings = []
    actions = []
    for item in packet.get("detectors", [])[:3]:
        detector_id = str(item.get("detector", ""))
        findings.append(DETECTOR_LABEL_KO.get(detector_id, "추가 비용이 발생할 수 있는 사용 패턴"))
        actions.append(ACTION_KO.get(detector_id, "같은 조건에서 변경 전·후를 다시 측정하세요."))
    if not findings:
        findings = ["측정된 비용과 품질 결과를 확인했습니다."]
    if not actions:
        actions = ["같은 입력과 품질 기준으로 결과를 재확인하세요."]

    if verdict == "PASS":
        headline = "비용은 줄고 품질 기준은 유지되었습니다."
    elif verdict == "NO_SAVINGS":
        headline = "품질은 확인됐지만 비용 절감은 확인되지 않았습니다."
    elif verdict == "FAIL":
        headline = "품질 또는 독립검증 기준을 통과하지 못했습니다."
    elif verdict == "NEEDS_EVIDENCE":
        headline = "판정에 필요한 측정 증거가 부족합니다."
    else:
        headline = "확정할 수 없는 값이 있어 절감 판정을 차단했습니다."

    return {
        "schema": "costdoctor.user-report.v1",
        "report_schema_version": "1.0.0",
        "generated_at": packet.get("generated_at"),
        "language": "ko",
        "title": "CostDoctor 비용·품질 진단 결과",
        "facts": facts,
        "summary_10_seconds": {
            "headline": headline,
            "result": verdict,
            "trust": trust,
            "next_action": actions[0],
        },
        "explanation_1_minute": {
            "what_changed": "동일한 작업 조건에서 변경 전과 변경 후를 반복 실행해 비용과 품질을 비교했습니다.",
            "why": findings,
            "recommended_actions": actions,
            "confidence": "독립검증 상태와 가격 확인 상태를 분리해 표시합니다.",
        },
        "details": {
            "measurement": "공개 결정형 시험 작업에서 실제 실행된 사용량만 계산했습니다.",
            "quality": "같은 품질 기준을 변경 전·후에 적용했습니다.",
            "rollback": "변경 전 상태 복원과 변경 후 재적용을 실제로 다시 실행했습니다.",
            "scope": "이 결과는 실행된 시험 작업 범위에만 적용되며 고객 운영비 절감을 뜻하지 않습니다.",
        },
        "privacy": {
            "source_code_included": False,
            "secret_included": False,
            "external_telemetry": False,
            "default_view_contains_internal_paths": False,
            "default_view_contains_hashes": False,
            "default_view_contains_raw_json": False,
        },
    }


def _shown(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    if isinstance(value, float):
        return format(value, ".9g")
    return str(value)


def _field(name: str, value: Any, suffix: str = "") -> str:
    return f'<span data-field="{escape(name)}">{escape(_shown(value))}</span>{escape(suffix)}'


def render_user_report_html(report: dict[str, Any], printable: bool = False) -> str:
    facts = report["facts"]
    summary = report["summary_10_seconds"]
    explanation = report["explanation_1_minute"]
    details = report["details"]
    mode = "print" if printable else "screen"
    findings = "".join(f"<li>{escape(item)}</li>" for item in explanation["why"])
    actions = "".join(f"<li>{escape(item)}</li>" for item in explanation["recommended_actions"])
    icon = "✓" if facts["verdict"] == "PASS" else "!" if facts["verdict"] in {"BLOCKED", "NEEDS_EVIDENCE"} else "×"
    return f"""<!doctype html>
<html lang="ko" data-render-mode="{mode}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(report['title'])}</title>
<style>
:root{{--ink:#17212a;--muted:#58647a;--line:#dce2ea;--paper:#fff;--soft:#f4f7fa;--accent:#e36b31;--primary:#164b79}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--soft);color:var(--ink);font:16px/1.65 "Pretendard","Apple SD Gothic Neo",system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:980px;margin:32px auto;padding:0 20px 48px}} header{{background:var(--primary);color:white;border-radius:8px;padding:28px}}
.eyebrow{{font-size:.82rem;letter-spacing:.08em;text-transform:uppercase;opacity:.78}} h1{{margin:.25rem 0;font-size:clamp(1.65rem,4vw,2.5rem)}}
.status{{display:flex;align-items:center;gap:12px;margin-top:16px}} .status-icon{{display:inline-grid;place-items:center;width:34px;height:34px;border:3px solid var(--accent);border-radius:50%;font-weight:800}}
.cards{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:18px 0}} .card,section{{background:var(--paper);border:1px solid var(--line);border-radius:8px;padding:18px}}
.label{{color:var(--muted);font-size:.86rem}} .value{{display:block;font-size:1.18rem;font-weight:750;margin-top:4px;overflow-wrap:anywhere}}
section{{margin-top:14px}} h2{{font-size:1.18rem;margin:0 0 10px}} ul{{padding-left:1.25rem}} .boundary{{color:var(--muted);font-size:.92rem}}
table{{width:100%;border-collapse:collapse}} th,td{{padding:9px;text-align:left;border-bottom:1px solid var(--line)}} th{{width:42%;color:var(--muted);font-weight:600}}
@media(max-width:700px){{main{{margin:16px auto;padding:0 12px 32px}}header{{padding:22px}}.cards{{grid-template-columns:1fr}}}}
@media print{{body{{background:white}}main{{max-width:none;margin:0;padding:0}}header{{border-radius:0;background:white;color:black;border-bottom:2px solid #111}}.card,section{{break-inside:avoid;box-shadow:none}}}}
</style>
</head>
<body><main>
<header><div class="eyebrow">10초 요약</div><h1>{escape(summary['headline'])}</h1>
<div class="status"><span class="status-icon" aria-hidden="true">{icon}</span><span>결과 {_field('verdict', facts['verdict'])}</span></div></header>
<div class="cards" aria-label="핵심 결과">
<div class="card"><span class="label">변경 전 비용</span><span class="value">$ {_field('before_cost_usd', facts['before_cost_usd'])}</span></div>
<div class="card"><span class="label">변경 후 비용</span><span class="value">$ {_field('after_cost_usd', facts['after_cost_usd'])}</span></div>
<div class="card"><span class="label">검증 절감액</span><span class="value">$ {_field('verified_savings_usd', facts['verified_savings_usd'])}</span></div>
<div class="card"><span class="label">절감률</span><span class="value">{_field('savings_rate_percent', facts['savings_rate_percent'], '%')}</span></div>
<div class="card"><span class="label">신뢰 수준</span><span class="value">{_field('trust_level', facts['trust_level'])}</span></div>
<div class="card"><span class="label">적용 상태</span><span class="value">{_field('application_state', facts['application_state'])}</span></div>
</div>
<section><h2>1분 설명</h2><p>{escape(explanation['what_changed'])}</p><h3>발견한 원인</h3><ul>{findings}</ul><h3>권장 행동</h3><ul>{actions}</ul><p>{escape(explanation['confidence'])}</p></section>
<section><h2>품질과 검증</h2><table>
<tr><th>변경 전 품질</th><td>{_field('quality_before', facts['quality_before'])}</td></tr>
<tr><th>변경 후 품질</th><td>{_field('quality_after', facts['quality_after'])}</td></tr>
<tr><th>품질 판정</th><td>{_field('quality_verdict', facts['quality_verdict'])}</td></tr>
<tr><th>독립검증</th><td>{_field('independent_validation', facts['independent_validation'])}</td></tr>
<tr><th>rollback</th><td>{_field('rollback_status', facts['rollback_status'])}</td></tr>
<tr><th>변경 전 가격</th><td>{_field('pricing_status_before', facts['pricing_status_before'])}</td></tr>
<tr><th>변경 후 가격</th><td>{_field('pricing_status_after', facts['pricing_status_after'])}</td></tr>
</table></section>
<section><h2>상세 근거</h2><p>{escape(details['measurement'])}</p><p>{escape(details['quality'])}</p><p>{escape(details['rollback'])}</p><p class="boundary">{escape(details['scope'])}</p></section>
</main></body></html>"""


def render_user_summary_markdown(report: dict[str, Any]) -> str:
    facts = report["facts"]
    summary = report["summary_10_seconds"]
    actions = report["explanation_1_minute"]["recommended_actions"]
    return "\n".join(
        [
            f"# {report['title']}",
            "",
            f"## 10초 요약: {summary['headline']}",
            "",
            f"- 결과: {facts['verdict']}",
            f"- 비용: ${_shown(facts['before_cost_usd'])} → ${_shown(facts['after_cost_usd'])}",
            f"- 검증 절감액: ${_shown(facts['verified_savings_usd'])}",
            f"- 절감률: {_shown(facts['savings_rate_percent'])}%",
            f"- 품질: {_shown(facts['quality_before'])} → {_shown(facts['quality_after'])} ({facts['quality_verdict']})",
            f"- 신뢰 수준: {facts['trust_level']}",
            f"- 적용 상태: {facts['application_state']}",
            "",
            "## 지금 할 일",
            "",
            *[f"- {item}" for item in actions],
            "",
            "> 이 결과는 실행된 시험 작업 범위에만 적용되며 고객 운영비 절감을 뜻하지 않습니다.",
            "",
        ]
    )
