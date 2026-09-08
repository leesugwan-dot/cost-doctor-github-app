# CostDoctor

**Free AI/LLM API Cost Review for GitHub — read-only.** Enter one public repository URL and receive a Static Precheck plus an evidence-bound deep diagnosis in the same Issue.

Free, read-only AI/LLM cost review for GitHub, with English as the default and Korean available.

[English](README.md) · [한국어 안내](README.ko.md)

**FREE** · **READ-ONLY** · **NO API KEY** · **NO CODE EXECUTION** · **NO CODE MODIFICATION** · **EXTERNAL TELEMETRY OFF**

## Start in seconds

- [Open the Pages Quick Scan](https://leesugwan-dot.github.io/cost-doctor-github-app/)
- [Open the trusted Issue Form fallback](https://github.com/leesugwan-dot/cost-doctor-github-app/issues/new?template=public-scan.yml)
- [Run a private-repository Self-Scan](docs/PRIVATE_REPO_SELF_SCAN.md)
- [Install the GitHub Marketplace Action](https://github.com/marketplace/actions/costdoctor-repository-review)

## What happens

1. Enter one **public GitHub repository URL**.
2. Choose English (the default) or 한국어.
3. Submit the trusted GitHub Issue Form.
4. Receive one CostDoctor comment containing Stage 1 Static Precheck and Stage 2 Deep Diagnosis.

The free path reads a bounded checkout in a temporary GitHub-hosted runner. It does not execute the target project, call an LLM/provider API, request a secret, write to the target repository, or send customer source to an operator computer.

## What the result means

The report orders findings as: candidate signal → runtime-impact evidence → safe repository location or call group → measurable token/context effect when available → concrete fix or measurement action → expected effect or why it cannot be estimated → confidence and unknowns.

Static evidence is not a bill, API usage receipt, or verified savings claim. Without matching provider usage, price, quality, and Before/After evidence, cost and savings stay `UNKNOWN`. Test, evaluation, documentation, inactive-retry, and ordinary-file-cache signals are not promoted to production cost loss without runtime support.

## Private repositories

Never paste a private URL into the public form. Use [Private Self-Scan](docs/PRIVATE_REPO_SELF_SCAN.md) inside your own GitHub Actions workflow.

| Boundary | Behavior |
| --- | --- |
| Permission | `contents: read` by default |
| Location | Your GitHub-hosted runner's temporary workspace |
| Writes | No commit, push, branch, PR, or merge |
| Provider calls | No API key or paid model required for structural diagnosis |
| Telemetry | External telemetry is off by default |

## Repeat checks with the Action

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

The Action writes a runner-local `report.json` and `report.md` and exposes `report-directory` and `scan-status` outputs. See the [Action start guide](costdoctor-entry/docs/START.md).

## Evidence and safety

- No automatic code fixes, commits, branches, pull requests, merges, pricing, or billing features are enabled.
- Public Scan and Private Self-Scan are read-only and fail closed on unsafe or incomplete input.
- Original source, secrets, prompts, private paths, and raw credentials are not placed in public results.
- Optional verified measurement uses the customer's own provider account, GitHub Secret, and an approved per-workload spend cap.

## Evidence-based guides

- [LLM cost optimization](docs/guides/llm-cost-optimization.md)
- [Retry cost](docs/guides/llm-retry-cost.md)
- [Prompt caching](docs/guides/prompt-cache-cost.md)
- [Token and context cost](docs/guides/token-context-cost.md)
- [Static-analysis boundary](docs/guides/static-analysis-boundary.md)

## Learn more

[Public Scan](docs/PUBLIC_SCAN.md) · [Private Self-Scan](docs/PRIVATE_REPO_SELF_SCAN.md) · [Sanitized result example](costdoctor-entry/examples/report.md) · [Quick Start](costdoctor-entry/docs/QUICKSTART_VISUAL.md) · [FAQ](costdoctor-entry/docs/FAQ.md) · [Rollback](costdoctor-entry/docs/ROLLBACK.md) · [Feedback](https://github.com/leesugwan-dot/cost-doctor-github-app/issues/new?template=feedback.yml)

[Privacy](PRIVACY.md) · [Terms](TERMS.md) · [Operator policy](OPERATOR_POLICY.md) · [Security](SECURITY.md) · [Support](SUPPORT.md) · [Apache-2.0 license](LICENSE)

CostDoctor is Apache-2.0 at the public integration layer. D5 automatic code changes, D7 paid features, and D9 external-provider automatic fixes are not advertised as available features.
