# CostDoctor

**Free AI/LLM API Cost Review for GitHub — read-only.** Enter one public URL and receive a Static Precheck plus a deeper, evidence-bound diagnosis in the same Issue.

한국어: **GitHub 프로젝트의 AI/LLM API 비용 낭비 신호를 무료로 확인합니다.** 공개 저장소는 주소 하나로 검사하고, 비공개 저장소는 본인의 GitHub Actions 안에서만 Self-Scan합니다.

**FREE** · **READ-ONLY** · **NO API KEY** · **NO CODE MODIFICATION** · **NO CUSTOMER SOURCE UPLOAD** · **EXTERNAL TELEMETRY OFF**

## Start here

[**Pages Quick Scan 화면 열기**](https://leesugwan-dot.github.io/cost-doctor-github-app/) · [**내 공개 GitHub 무료 검사하기 (Issue Form fallback)**](https://github.com/leesugwan-dot/cost-doctor-github-app/issues/new?template=public-scan.yml) · [**Private repository Self-Scan**](docs/PRIVATE_REPO_SELF_SCAN.md) · [**GitHub Marketplace에서 Action 설치**](https://github.com/marketplace/actions/costdoctor-repository-review)

공개 진단은 Provider Secret 없이 구조 진단과 가능한 무료 정량 측정을 자동으로 이어갑니다. 결과는 실제 runtime 비용 영향 후보와 안전한 위치, 가능한 토큰·비용 영향, 구체적인 측정 방법을 우선 표시합니다. 실제 비용·절감률은 같은 workload의 Provider usage Evidence가 있을 때만 검증됩니다. 고급 측정 경로는 [**Verified Savings workflow 안내**](docs/PUBLIC_VERIFIED_SAVINGS.md)를 참고하세요.

처음이라면 [Pages Quick Scan 화면](https://leesugwan-dot.github.io/cost-doctor-github-app/)에서 주소 하나를 입력해 안전한 GitHub 진단 양식으로 이동하세요. 브라우저에서 주소를 먼저 검사하며 credential·workflow·ref·runner·secret을 받지 않습니다.

### 10초 요약

- **무엇인가요?** 코드를 실행하지 않고 AI/LLM 비용 낭비 구조를 찾고 가능한 범위에서 정량화합니다.
- **무료인가요?** 공개 저장소 진단은 무료이며 API Key가 필요 없습니다.
- **코드가 바뀌나요?** 아니요. 자동 수정, commit, push, branch, PR, merge를 하지 않습니다.
- **코드를 가져가나요?** 고객 소스를 운영자 PC로 보내지 않습니다. 공개 진단은 GitHub-hosted runner의 임시 공간에서만 읽습니다.
- **어디서 시작하나요?** 공개 저장소는 위의 무료 검사 버튼, 비공개 저장소는 Self-Scan 안내를 누릅니다.

## 공개 저장소: 설치 없이 한 번 사용하기

1. [Pages Quick Scan 화면](https://leesugwan-dot.github.io/cost-doctor-github-app/)을 엽니다.
2. 검사할 **공개 GitHub 저장소 주소** 하나와 결과 언어를 입력합니다.
3. 브라우저 검증 후 열리는 trusted GitHub form에서 공개 결과 안내를 확인하고 제출합니다.
4. 완료되면 같은 Issue에 정리된 Stage 1 + Stage 2 결과와 검증 영수증이 남습니다.

Issue Form을 직접 쓰고 싶다면 [fallback 양식](https://github.com/leesugwan-dot/cost-doctor-github-app/issues/new?template=public-scan.yml)을 사용하세요.

공개 진단은 실제 API 호출·청구·절감액을 측정하지 않습니다. 정적 신호는 실행 중 낭비량이 아니며, 실제 비용·품질 주장은 별도 Provider Evidence 없이는 `UNKNOWN`입니다. 자세한 범위는 [공개 진단 안내](docs/PUBLIC_SCAN.md)를 보세요.

## 비공개 저장소: 내 Actions 안에서 Self-Scan

비공개 URL을 공개 스캐너에 붙여넣지 마세요. [Private repository Self-Scan 안내](docs/PRIVATE_REPO_SELF_SCAN.md)를 따라 본인 저장소의 Actions에서 실행합니다.

| 경계 | 동작 |
| --- | --- |
| 권한 | `contents: read` 기본 |
| 위치 | 고객 GitHub Actions의 임시 runner |
| 변경 | commit·push·branch·PR·merge 없음 |
| 전송 | 고객 source를 운영자 PC로 보내지 않음 |
| 비용 | API Key·유료 모델 필요 없음 |

## 무엇을 알려주나요?

| 신호 | 쉽게 말하면 |
| --- | --- |
| 모델 호출 후보 | 실제 호출과 SDK 설정을 구분해 확인 |
| 재시도 후보 | 활성 재시도와 비활성·문서 신호를 구분 |
| AI 요청 문맥 재사용 후보 | Provider 문맥 캐시와 일반 캐시를 분리 |
| 토큰·문맥 제한 후보 | 현재 구조와 줄일 후보를 정량 비교 |

### Sanitized 결과 예시

아래는 [검증용 공개 예시](costdoctor-entry/examples/report.md)의 요약입니다. 특정 프로젝트의 비용이나 절감률을 뜻하지 않습니다.

| 결과 카드 | 예시 |
| --- | ---: |
| MODEL CALLS | 101 후보 |
| RETRY RISK | 0 후보 |
| CACHE SIGNALS | 3 후보 |
| TOKEN LIMITS | 3 후보 |

**실제 비용·토큰 절감은 usage Evidence가 없으면 측정하지 않습니다.** 정적 신호는 후보이며, 보고서에는 근거 범위·신뢰도·점검 우선순위·안전 경계가 함께 표시됩니다. 내부 식별자와 원문 코드·비밀키·로컬 경로는 기본 결과에 넣지 않습니다.

## 반복 사용: GitHub Action

한 번 확인한 뒤 모든 변경에서 반복하려면 [Marketplace Action](https://github.com/marketplace/actions/costdoctor-repository-review)을 사용하세요.

```yaml
permissions:
  contents: read

steps:
  - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
    with:
      persist-credentials: false
  - name: Review AI cost signals
    uses: leesugwan-dot/cost-doctor-github-app@v1.0.1
```

Action은 runner-local `report.json`과 `report.md`를 만들고 `report-directory`, `scan-status` 출력을 제공합니다. 상세 설정은 [Action 시작 안내](costdoctor-entry/docs/START.md)를 보세요.

## 안전성과 주장 범위

CostDoctor는 다음을 하지 않습니다.

- 대상 프로젝트 코드를 실행하거나 저장소에 쓰지 않습니다.
- 자동 수정, PR, merge, 가격·결제 기능을 켜지 않습니다.
- 정적 신호를 검증된 절감액으로 표시하지 않습니다.
- 무료 진단에서 API Key를 요구하거나 고객 source를 외부 AI Provider로 보내지 않습니다.

실제 Provider 측정은 별도 선택형 범위이며 고객 자신의 계정·GitHub Secret·작업별 지출한도가 필요합니다. [Universal 측정·검증 문서](universal/README.md)는 무료 정적 진단과 분리된 Evidence 경계를 설명합니다.

## 개인정보와 사용자 Evidence

외부 telemetry는 기본 OFF입니다. 저장소에 포함된 보고 workflow가 있다면 공개 진단 요청·성공 실행·피드백의 **집계 수치만** 다루며 사용자명, Issue 본문, source, 파일명, 비밀값, private 활동을 추적하지 않습니다. [보고 방식](docs/USER_EVIDENCE_REPORTING.md) · [개인정보 보호 피드백](https://github.com/leesugwan-dot/cost-doctor-github-app/issues/new?template=feedback.yml)

## 문서

[무료 공개 진단](docs/PUBLIC_SCAN.md) · [Private Self-Scan](docs/PRIVATE_REPO_SELF_SCAN.md) · [결과 예시](costdoctor-entry/examples/report.md) · [시작 안내](costdoctor-entry/docs/START.md) · [시각 Quick Start](costdoctor-entry/docs/QUICKSTART_VISUAL.md) · [화면 가이드](costdoctor-entry/docs/SCREEN_GUIDE.md) · [FAQ](costdoctor-entry/docs/FAQ.md) · [문제 해결](costdoctor-entry/docs/TROUBLESHOOTING.md) · [중지·Rollback](costdoctor-entry/docs/ROLLBACK.md)

[Privacy](PRIVACY.md) · [Terms](TERMS.md) · [Operator policy](OPERATOR_POLICY.md) · [Security](SECURITY.md) · [Support](SUPPORT.md) · [Apache-2.0 license](LICENSE)

과거 GitHub App 조사 자료는 [legacy reference](docs/LEGACY_GITHUB_APP_REFERENCE.md)로만 보존하며 현재 설치 경로가 아닙니다.
