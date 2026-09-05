# CostDoctor 운영정책

상태: `CURRENT_FREE_BETA_POLICY`

## 현재 확정

- 서비스 표시명: **CostDoctor**
- 일반 지원 URL: https://github.com/leesugwan-dot/cost-doctor-github-app/issues
- 기본 지원 언어: 한국어 + English
- 기본 준거 기준: 대한민국
- CostDoctor 자체 외부 telemetry: 기본 OFF
- 고객 source의 운영자 개인 PC 저장: 금지
- 공개 저장소: GitHub-hosted runner의 제한된 정적 진단
- Private Repository: 사용자 GitHub Actions 내부의 읽기 전용 Self-Scan을 기본 방식으로 채택
- Private Repository 기본 권한: `contents: read`
- 비밀키: 고객 자신의 GitHub Secret 사용
- 실제 유료 API 실행: 작업별 최대 지출한도 사전 승인 필수
- 무료 베타 SLA: 보장 없음 / best-effort
- 공개 저장소 코드·문서 라이선스: Apache-2.0
- 비공개 상용 최적화 핵심: 공개 저장소 라이선스 범위 밖

## 현재 보류

다음은 외부 반응과 추가 Evidence를 본 뒤 결정합니다.

1. 자동 코드 수정/branch/PR 공개 기능
2. 유료화 방식·가격·환불정책
3. AI 자동수정 시 외부 AI Provider 사용방식과 코드 전송 경계

보류 항목은 준비 코드·설계가 존재하더라도 사용자 기능으로 활성화하거나 완료로 주장하지 않습니다.

## Marketplace

무료 진단을 먼저 GitHub Marketplace에 노출하는 방향을 채택합니다. 기술·문서·권한 준비는 자동으로 진행하되, GitHub가 요구하는 계정 소유자 약관 동의·Marketplace 제출 버튼·스토어 심사 등 외부 UI 행위는 실제 소유자 작업으로 남깁니다.

## 유료 측정

향후 실제 Before/After API 측정에서는 고객 API Key를 운영자에게 보내지 않습니다. 고객 GitHub Secret에서 사용하고, 실행 전에 통화·최대 지출한도·측정 범위를 명시적으로 승인받습니다. 승인 범위를 벗어날 가능성이 있으면 fail-closed로 중단합니다.

## 변경 원칙

권한 확대, 외부 전송, 데이터 보존 확대, 결제 도입, 자동 저장소 쓰기 기능은 조용히 활성화하지 않습니다. 먼저 문서·계약·검증경계를 갱신하고 사용자에게 필요한 승인 지점을 분명히 표시합니다.
