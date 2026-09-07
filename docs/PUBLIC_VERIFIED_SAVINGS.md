# Public Verified Savings 실행

이 workflow는 기존 정적 Public Scan을 대체하지 않고, 한 번의 실행에서 모든 일반 GitHub 저장소에 같은 두 단계 결과를 제공합니다.

1. Stage 1: 대상 저장소 checkout에 결속된 정적 Precheck
2. Stage 2: 구체적인 비용 낭비 후보, 개선 방법, 예상 영향, 검증 가능한 Evidence 등급

Provider와 모델은 Registry/Adapter에서 자동 탐지합니다. OpenAI, Anthropic, Gemini, Azure OpenAI, Bedrock, Upstage, OpenAI-compatible, Local/Ollama 및 unknown/custom을 구조적으로 확장할 수 있습니다. Upstage/Solar는 지원 adapter 중 하나일 뿐 기본 대상이 아닙니다.

Provider Secret이 없어도 Stage 2는 `STRUCTURAL_DIAGNOSIS`, 가능한 경우 `DETERMINISTIC_MEASUREMENT` 또는 `ESTIMATED_COST_SAVINGS`까지 계속 생성합니다. 실제 usage·공식 가격·동일 workload 품질검사·독립검증이 모두 있을 때만 `VERIFIED_SAVINGS`로 승격합니다. 정적 수치, byte proxy, CostDoctor 자체 fixture는 사용자 저장소 절감으로 승격하지 않습니다.

실제 Provider 경로를 선택할 때만 대상 저장소 Secret 이름을 workflow input으로 지정하고, 정확한 실행 확인값과 승인된 지출한도를 사용합니다. Secret 원문·prompt·응답은 로그·artifact·Issue에 저장하지 않습니다.

실제 대상 저장소에는 commit, push, branch, PR, merge를 하지 않습니다. 개선 검증은 runner-local Shadow 범위에서만 수행합니다.
