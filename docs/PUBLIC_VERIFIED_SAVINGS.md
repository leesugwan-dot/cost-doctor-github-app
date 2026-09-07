# Public Verified Savings 실행

이 workflow는 기존 정적 Public Scan을 대체하지 않고, 한 번의 수동 실행에서 다음 결과를 하나의 안전한 보고서로 묶습니다.

1. 대상 저장소 checkout에 결속된 정적 Precheck
3. 기존 OpenAI fixture는 `ENGINE_SELF_TEST/PROVIDER_REFERENCE`로만 보관
4. 대상 저장소의 Solar/Upstage workload가 발견될 때만 RAW → ENGINE → ENGINE+COSTDOCTOR 실행
5. 품질·rollback/reapply·독립검증 상태
6. 실제 Provider 사용량이 있을 때만 비용과 절감률 표시

GitHub Actions의 **CostDoctor public verified savings** workflow에서 `target_repository`와 `target_ref`를 확인하세요. 대상 Provider 측정은 대상 저장소의 `UPSTAGE_API_KEY` Secret, `solar-pro3`, 정확한 실행 확인값, 지출한도가 모두 맞아야 합니다. Secret은 로그·artifact·Issue에 저장하지 않습니다.

Secret·대상 workload·공식 usage/가격이 없으면 결과는 `NEEDS_ACTION`/`UNKNOWN`으로 남습니다. 정적 신호 수, byte proxy, OpenAI fixture 가격을 대상 저장소 절감으로 해석하지 않습니다.

실제 대상 저장소에는 commit, push, branch, PR, merge를 하지 않습니다. 개선 검증은 runner-local Shadow 범위에서만 수행합니다.
