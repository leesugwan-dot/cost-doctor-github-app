# AI 자동수정 실행방식 — 현재 보류

상태: `DEFERRED_UNTIL_USER_REACTION / NOT_ENABLED`

외부 AI Provider를 사용해 고객 코드를 자동 수정하는 방식은 현재 공개 기능으로 활성화하지 않습니다.

보류 대상:

- 어떤 AI Provider를 지원할지
- 고객 코드의 외부 Provider 전송 범위
- 고객이 Provider를 선택하는 방식
- Provider별 Secret/비용/보존정책
- AI 수정과 비-AI 결정형 수정의 우선순위

현재 유지하는 경계:

- 고객 코드를 CostDoctor 운영자의 개인 PC에 저장하지 않음
- 공개 진단에서 외부 AI 호출 없음
- AI Provider로 고객 코드를 자동 전송하지 않음
- D9가 다시 승인되기 전에는 AI 자동수정을 공개 기능으로 광고하지 않음
- 실제 API 측정용 D8 비용정책과 D9 자동수정 방식은 별도 결정으로 유지

재검토는 무료 진단/Private Self-Scan 사용자 반응이 충분히 쌓인 뒤 진행합니다.
