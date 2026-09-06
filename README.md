# CostDoctor — Free AI/LLM API Cost Review for GitHub

[![GitHub Marketplace](https://img.shields.io/badge/Marketplace-CostDoctor-2ea44f?logo=github)](https://github.com/marketplace/actions/costdoctor-repository-review)
[![Release](https://img.shields.io/github/v/release/leesugwan-dot/cost-doctor-github-app)](https://github.com/leesugwan-dot/cost-doctor-github-app/releases/latest)
[![Root Action self-test](https://github.com/leesugwan-dot/cost-doctor-github-app/actions/workflows/root-action-selftest.yml/badge.svg)](https://github.com/leesugwan-dot/cost-doctor-github-app/actions/workflows/root-action-selftest.yml)
[![Public scan self-test](https://github.com/leesugwan-dot/cost-doctor-github-app/actions/workflows/public-scan-selftest.yml/badge.svg)](https://github.com/leesugwan-dot/cost-doctor-github-app/actions/workflows/public-scan-selftest.yml)
[![CodeQL](https://github.com/leesugwan-dot/cost-doctor-github-app/actions/workflows/codeql.yml/badge.svg)](https://github.com/leesugwan-dot/cost-doctor-github-app/actions/workflows/codeql.yml)
[![License](https://img.shields.io/github/license/leesugwan-dot/cost-doctor-github-app)](LICENSE)

Find static AI and model API cost-risk signals before they become expensive: model calls, retry loops, missing cache signals, and token-limit risks.

**Free · read-only · no API key · no target-code execution · no customer source upload · external telemetry off**

[**Run a free public repository scan**](https://github.com/leesugwan-dot/cost-doctor-github-app/issues/new?template=public-scan.yml) · [**Use the Marketplace Action**](https://github.com/marketplace/actions/costdoctor-repository-review) · [**Private repository Self-Scan**](docs/PRIVATE_REPO_SELF_SCAN.md)

한국어: 공개 GitHub 주소 하나를 입력하면 AI/LLM API 비용 관련 정적 신호를 무료로 확인합니다. 비공개 저장소는 고객 자신의 GitHub Actions 안에서 `contents: read`로 Self-Scan합니다.

## What CostDoctor reports

| Signal | What it helps you review |
| --- | --- |
| `MODEL_CALL` | AI/LLM or model API call sites |
| `RETRY_LOOP` | Retry patterns that may multiply calls and cost |
| `CACHE_SIGNAL` | Cache-related signals worth checking |
| `TOKEN_LIMIT` | Token or output-limit controls |

These are review signals, not billing measurements. Actual calls, spend, savings, and quality improvements remain `UNKNOWN` without measured Before/After Evidence.

## Fastest path: paste one public GitHub URL

1. Open [Free Public Repository Scan](https://github.com/leesugwan-dot/cost-doctor-github-app/issues/new?template=public-scan.yml).
2. Paste one public GitHub repository URL.
3. Choose Korean or English and submit the Issue.
4. CostDoctor runs a bounded static scan on a GitHub-hosted runner, posts a sanitized result and verification receipt, and closes the request.

The target project is not executed or sent to the operator's personal computer. Source text, filenames, secrets, and local paths are not included in the public result.

## Use as a GitHub Action

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

The Action writes sanitized `report.json` and `report.md` files to a runner-local directory and exposes `report-directory` and `scan-status` outputs.

## Private repositories

Do not paste a private repository URL into the public scanner. Install the [read-only Self-Scan workflow](costdoctor-entry/private-repo-selfscan.yml) inside the repository owner's GitHub Actions environment instead.

- Default permission: `contents: read`
- No automatic commit, push, branch, pull request, or merge
- No customer source transfer to the operator
- No external telemetry by default

[Private Self-Scan guide](docs/PRIVATE_REPO_SELF_SCAN.md)

## Safety and claim boundaries

CostDoctor does not:

- execute target-project code;
- write to the scanned repository;
- upload customer source to an operator PC;
- require an AI provider key for static review;
- claim verified savings from static signals;
- enable automatic fixes, pricing, payments, or external AI-provider code transfer.

Future measured API runs, if separately offered, require the customer's own provider account, a GitHub Secret, and an explicit per-run maximum spend approval.

## Privacy-safe user Evidence

External telemetry remains off. A repository-native workflow reports only aggregate counts for public scan requests, successful public scan runs, and public feedback. It never writes usernames, user Issue bodies or comments, source, filenames, secrets, or private-repository activity. It reads only its own tracking-Issue marker to avoid duplicate notifications.

[How user Evidence reporting works](docs/USER_EVIDENCE_REPORTING.md) · [Share privacy-safe feedback](https://github.com/leesugwan-dot/cost-doctor-github-app/issues/new?template=feedback.yml)

## Documentation

[Public scan guide](docs/PUBLIC_SCAN.md) · [Visual quick start](costdoctor-entry/docs/QUICKSTART_VISUAL.md) · [Screen guide](costdoctor-entry/docs/SCREEN_GUIDE.md) · [Result example](costdoctor-entry/examples/report.md) · [FAQ](costdoctor-entry/docs/FAQ.md) · [Troubleshooting](costdoctor-entry/docs/TROUBLESHOOTING.md) · [Rollback](costdoctor-entry/docs/ROLLBACK.md)

[Universal offline usage Evidence, Registry pricing, benchmark, quality guard, routing advice, and independent validation](universal/README.md)

[Privacy](PRIVACY.md) · [Terms](TERMS.md) · [Operator policy](OPERATOR_POLICY.md) · [Security](SECURITY.md) · [Support](SUPPORT.md) · [Apache-2.0 license](LICENSE)

Earlier GitHub App research is preserved separately as [legacy reference material](docs/LEGACY_GITHUB_APP_REFERENCE.md); it is not the current Marketplace Action.
