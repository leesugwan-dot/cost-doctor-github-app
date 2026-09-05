# CostDoctor 실제 Before/After 측정 정책

상태: `POLICY_APPROVED / PROVIDER_EXECUTION_NOT_ENABLED`

이 정책은 향후 CostDoctor가 실제 API/모델 호출을 사용해 Before/After 비용·토큰·품질을 측정할 때 적용합니다. 현재 무료 공개 정적 진단에는 유료 API 호출이 없습니다.

## 기본 원칙

1. API 계정은 고객 소유입니다.
2. API Key는 고객 자신의 GitHub Secret에 저장합니다.
3. CostDoctor 운영자에게 API Key를 전달하지 않습니다.
4. 실행 전 고객이 Provider, 모델, 측정 범위, 최대 지출한도를 명시적으로 승인해야 합니다.
5. 가격 또는 사용량을 신뢰할 수 없으면 유료 실행을 시작하지 않습니다.
6. 예상 최대 비용이 승인 한도를 넘으면 fail-closed로 중단합니다.
7. Before/After는 동일 목표·입력·모델·품질 기준으로 비교해야 합니다.
8. 비용이 줄어도 품질·완료율이 낮아지면 성공으로 판정하지 않습니다.

## 예산 가드

저장소에는 `.github/scripts/budget_guard.py`가 포함되어 있습니다. 이 가드는 Provider를 호출하지 않고 실행 전 승인한도만 확인합니다.

예시:

```bash
python3 .github/scripts/budget_guard.py \
  --limit-usd 5 \
  --spent-usd 1.25 \
  --next-max-usd 2
```

허용 결과는 `ALLOW_WITHIN_APPROVED_BUDGET`, 차단 결과는 `BLOCK_BUDGET`입니다.

이 가드가 허용했다고 실제 Provider 호출이 자동 승인되는 것은 아닙니다. Provider별 가격·사용량 결속과 실제 실행기 구현은 별도 검증이 필요합니다.

## 현재 보류 항목과의 관계

- 자동 코드 수정/PR 기능: 보류
- AI 자동수정 Provider 방식: 보류
- CostDoctor 유료화 가격·과금: 보류

따라서 현재 정책 확정은 **향후 측정 시 고객 비밀키와 비용을 안전하게 다루는 원칙**만 고정하며, 실제 유료 Provider 실행이나 고객 결제를 활성화하지 않습니다.
