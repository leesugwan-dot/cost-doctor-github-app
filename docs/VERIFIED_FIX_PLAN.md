# CostDoctor Verified Fix — 안전한 자동수정/PR 경계

상태: `DESIGN_READY_NOT_ENABLED`

## 목표

CostDoctor가 문제 후보를 찾는 데서 끝나지 않고, **수정안을 만들고 실제 Before/After와 품질을 검증한 뒤 사용자가 원할 때만 PR로 올리는 구조**입니다.

## 기본 원칙

자동화 범위는 최대화하되 실제 repository 쓰기는 마지막 승인 경계로 분리합니다.

1. 진단 — 자동, 읽기 전용
2. 수정안 생성 — 자동, 격리 작업공간
3. 테스트 — 자동
4. Before/After 측정 — 자동. 단, 외부 API 비용·비밀키가 필요하면 사용자 경계
5. 품질·회귀검증 — 자동
6. 수정안/증거 패키지 생성 — 자동
7. branch/PR 게시 — **사용자 승인 후에만**
8. merge — **자동 금지, 사용자가 결정**

## 권한 추천

### 기본 진단 모드

`contents: read`만 사용합니다.

### Verified Fix 게시 모드

PR을 실제로 만들 때만 최소한의 쓰기 권한을 별도 승인받습니다. 기본 branch 직접 overwrite보다 **새 branch + PR**을 원칙으로 합니다.

추천 경계:

- `contents: write`: 승인된 fix branch에만 사용
- `pull_requests: write`: 승인된 PR 생성/갱신에만 사용
- issue/comment 쓰기: 필수일 때만 별도 검토
- checks: 결과 표시가 필요할 때만
- administration/secrets: 요구하지 않음

GitHub App을 사용할 경우 진단용 read-only App과 쓰기 가능한 Fix 경로를 분리하거나, 권한 상승 시 GitHub의 재승인을 요구하는 구조가 안전합니다.

## 성공 판정

`수정됨`만으로 성공이 아닙니다.

성공은 최소 다음이 모두 필요합니다.

- 같은 목표·입력·모델·환경의 Before/After 비교
- 비용/토큰 또는 실행효율 개선 Evidence
- 품질/완료율 저하 없음
- 회귀검사 PASS
- 독립 검증
- 되돌리기 가능

증거가 없으면 절감액은 `UNKNOWN`으로 유지합니다.

## 자동 merge를 기본 금지하는 이유

테스트 PASS와 실제 사업·제품 의도에 맞는 변경은 같은 의미가 아닙니다. 특히 비용 최적화는 품질, 지연시간, 안정성, 개인정보 경계와 충돌할 수 있으므로 최종 merge는 repository 소유자가 결정하도록 합니다.

## 현재 구현 상태

이 문서와 `verified_fix_contract.json`은 권한·검증 경계를 고정한 준비물입니다. 실제 범용 자동수정 엔진과 외부 repository PR actual-run은 아직 이 공개 기능에 연결하지 않습니다.
