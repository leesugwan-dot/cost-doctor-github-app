# CostDoctor Verified Fix — 공개 예정 후보 / 현재 보류

상태: `PUBLIC_CANDIDATE_DEFERRED_UNTIL_USER_REACTION`

## 현재 결정

Verified Fix의 안전경계와 설계는 유지하지만 **현재 일반 사용자 기능으로 활성화하지 않습니다.** 무료 공개 진단과 Private Repository Self-Scan의 실제 반응·사용성·가치 Evidence를 본 뒤 공개 여부와 쓰기 권한 범위를 다시 결정합니다.

## 보류 중에도 유지할 안전경계

향후 공개를 검토할 때도 아래 원칙은 기본값으로 유지합니다.

1. 진단 — 읽기 전용
2. 수정안 생성 — 격리 작업공간
3. 테스트 — 자동 가능
4. Before/After — 실제 Evidence 필요
5. 품질·회귀검증 — 비용만 줄고 품질이 낮아지면 성공 아님
6. 수정안/증거 패키지 — 저장소 write 없이 준비 가능
7. branch/PR 게시 — 실제 공개 시 별도 명시적 사용자 승인
8. merge — 자동 금지

## 금지 경계

- 기본 branch 직접 overwrite 금지
- 자동 merge 금지
- 실제 절감 Evidence 없이 절감률 주장 금지
- 품질 하락을 비용절감 성공으로 승격 금지
- secret을 공개 Issue/보고서에 출력 금지

## 현재 구현 상태

`verified_fix_contract.json`은 이 보류상태와 안전경계를 기계가 읽을 수 있게 고정합니다. 실제 범용 자동수정/PR 기능은 현재 공개 제품 경로에 연결하지 않습니다.

## 재검토 시점

외부 사용자의 무료 공개 진단과 Private Self-Scan 반응이 충분히 쌓여 다음을 판단할 수 있을 때 재검토합니다.

- 사용자가 실제 자동수정을 원하는지
- 읽기 전용 진단만으로 충분한지
- 어떤 쓰기 권한이 신뢰를 해치지 않는지
- PR 생성이 실제 사용자 가치를 높이는지
