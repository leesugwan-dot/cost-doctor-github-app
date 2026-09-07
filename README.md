# CostDoctor

**Free AI/LLM API Cost Review for GitHub — read-only.** Find model-call, retry, cache, and token-limit signals before they become expensive.

한국어: **GitHub 프로젝트의 AI/LLM API 비용 낭비 신호를 무료로 확인합니다.** 공개 저장소는 주소 하나로 검사하고, 비공개 저장소는 본인의 GitHub Actions 안에서만 Self-Scan합니다.

**FREE** · **READ-ONLY** · **NO API KEY** · **NO CODE MODIFICATION** · **NO CUSTOMER SOURCE UPLOAD** · **EXTERNAL TELEMETRY OFF**

## Start here

[**내 공개 GitHub 무료 검사하기**](https://github.com/leesugwan-dot/cost-doctor-github-app/issues/new?template=public-scan.yml) · [**Private repository Self-Scan**](docs/PRIVATE_REPO_SELF_SCAN.md) · [**GitHub Marketplace에서 Action 설치**](https://github.com/marketplace/actions/costdoctor-repository-review)

실제 사용량·품질까지 한 번에 확인하려면 [**Verified Savings workflow 안내**](docs/PUBLIC_VERIFIED_SAVINGS.md)를 참고하세요. Provider Secret이 없어도 구체적인 Stage 2 구조진단·예상효과를 제공하며, 실제 비용·절감률은 usage Evidence가 있을 때만 VERIFIED로 승격됩니다.

처음이라면 [Pages-ready 소개 화면](docs/index.html)에서 20초 요약을 확인하세요.

### 10초 요약

- **무엇인가요?** 코드를 실행하지 않고 AI/LLM API 비용과 관련된 정적 검토 신호를 찾습니다.
- **무료인가요?** 공개 저장소 진단은 무료이며 API Key가 필요 없습니다.
- **코드가 바뀌나요?** 아니요. 자동 수정, commit, push, branch, PR, merge를 하지 않습니다.
- **코드를 가져가나요?** 고객 소스를 운영자 PC로 보내지 않습니다. 공개 진단은 GitHub-hosted runner의 임시 공간에서만 읽습니다.
- **어디서 시작하나요?** 공개 저장소는 위의 무료 검사 버튼, 비공개 저장소는 Self-Scan 안내를 누릅니다.

## 공개 저장소: 설치 없이 한 번 사용하기

1. [무료 공개 저장소 진단 시작](https://github.com/leesugwan-dot/cost-doctor-github-app/issues/new?template=public-scan.yml)을 엽니다.
2. 검사할 **공개 GitHub 저장소 주소** 하나를 붙여넣습니다.
3. 한국어 또는 English를 선택하고 제출합니다.
4. 완료되면 같은 Issue에 정리된 결과와 검증 영수증이 남습니다.

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
| `MODEL_CALL` | 모델/API 호출 후보가 있는 곳 |
| `RETRY_LOOP` | 실패 시 호출이 늘어날 수 있는 재시도 패턴 |
| `CACHE_SIGNAL` | 캐시를 확인해 볼 만한 신호 |
| `TOKEN_LIMIT` | 입력·출력 길이 제한을 확인할 신호 |

### Sanitized 결과 예시

아래는 [검증용 공개 예시](costdoctor-entry/examples/report.md)의 요약입니다. 특정 프로젝트의 비용이나 절감률을 뜻하지 않습니다.

| 결과 카드 | 예시 |
| --- | ---: |
| MODEL CALLS | 101 후보 |
| RETRY RISK | 0 후보 |
| CACHE SIGNALS | 3 후보 |
| TOKEN LIMITS | 3 후보 |

**실제 비용·토큰 절감: UNKNOWN.** 정적 신호 개수는 실제 호출 수나 낭비액이 아닙니다. 원문 코드·비밀키·로컬 경로는 결과에 넣지 않습니다.

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
