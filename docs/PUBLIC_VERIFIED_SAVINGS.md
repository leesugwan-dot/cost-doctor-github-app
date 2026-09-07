# Public Verified Savings 실행

이 workflow는 기존 정적 Public Scan을 대체하지 않고, 한 번의 수동 실행에서 다음 결과를 하나의 안전한 보고서로 묶습니다.

1. 정적 Precheck
2. 동일 조건의 RAW → ENGINE → ENGINE+COSTDOCTOR fixture 검증
3. Provider Secret preflight
4. 품질·rollback/reapply·독립검증 상태
5. 실제 Provider 사용량이 있을 때만 비용과 절감률 표시

GitHub Actions의 **CostDoctor public verified savings** workflow를 실행하세요. 실제 Provider 측정은 대상 저장소의 `OPENAI_API_KEY` Secret과 정확한 실행 확인값이 모두 있어야 합니다. Secret은 로그·artifact·Issue에 저장하지 않습니다.

Secret 또는 공식 usage/가격이 없으면 결과는 `NEEDS_ACTION`/`UNKNOWN`으로 남습니다. 정적 신호 수, byte proxy, fixture 가격을 실제 절감으로 해석하지 않습니다.

실제 대상 저장소에는 commit, push, branch, PR, merge를 하지 않습니다. 개선 검증은 runner-local Shadow 범위에서만 수행합니다.
