# CostDoctor 공개·운영 Gate

## 현재 무료 공개 진단 / GitHub Action

상태: `PUBLIC_BETA_ENABLED / MARKETPLACE_READY_FOR_OWNER_RELEASE / PRODUCTION_AUTHORITY_FALSE`

### 완료

1. 공개 GitHub URL 진단 actual GitHub-hosted 실행
2. 대상 코드 미실행 / 대상 저장소 write 없음
3. exact default-branch HEAD 결속
4. sanitized result + receipt + 짧은 Artifact 보존
5. 자동 회귀검사 + CodeQL
6. Apache-2.0 LICENSE + NOTICE
7. PRIVACY.md / TERMS.md / OPERATOR_POLICY.md
8. 지원/삭제 요청 경로
9. Private Repository read-only Self-Scan 기본방식 결정 및 template 준비
10. 실제 API 측정 시 고객 Secret + 명시적 최대 지출한도 원칙 및 budget guard
11. 루트 `action.yml` + root Action actual CI PASS
12. 정적 신호만으로 절감액을 주장하지 않고 Evidence 없으면 `UNKNOWN` 유지

### 외부 소유자 행동이 남은 항목

1. GitHub Marketplace Developer Agreement가 요구되면 repository 소유자가 동의
2. 루트 `action.yml`에서 `v1.0.0` Release 초안 생성
3. `Publish this Action to the GitHub Marketplace` 선택 후 Release 게시
4. 실제 외부 Private Repository 소유자의 설치·실행 승인 후 재현성 actual-run

## 의도적으로 보류된 제품 기능

외부 사용자 반응을 본 뒤 결정합니다.

- D5 자동 코드 수정/branch/PR 공개 기능
- D7 유료화 방식·가격·환불
- D9 외부 AI Provider 기반 자동수정/코드 전송 방식

보류 기능은 구현 준비나 설계가 존재하더라도 현재 공개 기능으로 표시하지 않습니다.

## 기존 GitHub App 후보

기존 App/webhook/Check Run 후보의 과거 내부 격리 E2E Evidence는 보존합니다. 해당 후보가 자동으로 Production Authority나 외부 사용성 검증을 획득한 것으로 승격하지 않습니다. 현재 일반 사용자 진입점은 무료 공개 URL 진단과 GitHub Action/Self-Scan 경로입니다.

## 주장 경계

- 실제 사용량 Evidence가 없으면 비용·토큰 절감은 `UNKNOWN`입니다.
- 실제 Before/After와 품질/완료율 검증 전에는 Verified Savings를 주장하지 않습니다.
- 판매·정산·유료 제품 완료는 D7 보류 해제 전까지 주장하지 않습니다.
