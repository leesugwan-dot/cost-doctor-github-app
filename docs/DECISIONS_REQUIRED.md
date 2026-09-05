# CostDoctor — 현재 결정 상태

상태: `APPROVED_WITH_THREE_DEFERRED_ITEMS`

## 확정 완료

### D1. 공개 라이선스 — 승인

- 공개 GitHub 연동/진단 계층: **Apache-2.0**
- 이 저장소에 포함되지 않은 상용 최적화 핵심: 별도 비공개 유지
- `LICENSE`와 `NOTICE` 적용

### D2. 운영자 표시·문의 채널 — 승인

- 서비스 표시명: **CostDoctor**
- 공식 일반 지원 URL: https://github.com/leesugwan-dot/cost-doctor-github-app/issues
- 민감정보는 공개 Issue에 게시 금지
- 유료화 전 법적으로 필요한 사업자/결제 표시는 별도 확정

### D3. 개인정보·이용조건 — 승인

- 기본 준거 기준: 대한민국
- CostDoctor 자체 외부 telemetry: 기본 OFF
- 고객 source의 운영자 개인 PC 저장: 금지
- 공개 Repo는 GitHub-hosted runner에서 제한된 정적 분석
- Private Repo는 사용자 GitHub Actions 내부 처리 우선
- 무료 베타 SLA: 보장 없음 / best-effort
- 공개 결과/Artifact 보존은 최소화하고 GitHub 정책을 따름
- 현 정책은 `PRIVACY.md`, `TERMS.md`, `OPERATOR_POLICY.md`에 반영

### D4. Private Repository 기본 방식 — 승인

- **사용자 private repo 안에서 GitHub Actions Self-Scan**을 기본으로 채택
- 기본 권한: `contents: read`
- 운영자 PC/서버로 원문 소스 전송·영속 저장하지 않음
- 자동 쓰기 없음
- 실제 외부 private repo 소유자의 설치/실행 검증은 해당 소유자 승인 후 진행

### D6. Marketplace 공개 — 승인

- 무료 진단부터 Marketplace에 노출하는 방향 채택
- 루트 `action.yml`, 설명, 라이선스, 개인정보, 약관, 지원문서 준비
- GitHub 계정 소유자의 Marketplace 약관 동의/제출 버튼/심사 대응은 외부 UI 행위이므로 자동 우회하지 않음

### D8. 실제 API 측정 비용 원칙 — 승인

- 고객 자신의 API 계정 사용
- Key는 고객 GitHub Secret에 저장
- 운영자에게 Key 전달 금지
- 작업별 Provider/모델/최대 지출한도 명시적 승인 필수
- 가격/사용량 불명확 또는 승인한도 초과 가능 시 fail-closed
- `.github/scripts/budget_guard.py`와 `measured_run_contract.json`으로 기본 경계 구현

## 반응을 본 뒤 결정할 보류 항목

### D5. 자동 수정 권한 — 보류

자동 코드 수정/branch/PR 기능은 **공개 예정 후보**로 설계와 안전경계만 유지합니다. 현재 일반 사용자 기능으로 활성화하지 않습니다.

계속 유지할 안전경계:

- 기본 branch 직접 overwrite 금지
- 자동 merge 금지
- 향후 활성화 시 실제 repository write 전 명시적 승인

### D7. 유료화 — 보류

무료 진단 반응과 외부 가치 Evidence를 본 뒤 결정합니다. 현재 가격·과금·환불정책을 확정하지 않고 결제 기능도 활성화하지 않습니다.

### D9. AI 자동수정 실행방식 — 보류

외부 AI Provider 사용, 고객 코드 전송 범위, Provider 선택방식은 반응을 본 뒤 결정합니다. 현재 외부 AI를 이용한 고객 코드 자동수정 기능으로 활성화하지 않습니다.

## 지금 남은 외부 행동

결정은 끝났지만 기술적으로 대신할 수 없는 외부 행동은 다음입니다.

1. GitHub Marketplace 소유자 약관/Listing UI 확인 및 실제 제출
2. 실제 외부 사용자의 Private Repository에서 Self-Scan 설치·실행 승인 및 재현성 검증
3. D5/D7/D9 재검토는 사용자 반응이 쌓인 뒤 수행
