# CostDoctor Universal Engine R1

This additive, offline engine turns runtime usage exports into evidence-bound cost diagnostics. It does not replace or weaken the existing public Action or private read-only Self-Scan.

## Safety boundary

- Offline import is the default; the engine contains no network client and makes no provider call.
- Prompts, responses, message bodies, raw source, secret fields, and recognized key patterns are rejected during ingest.
- Unknown models are tolerated. Unknown prices or billed dimensions stay `UNKNOWN` and cannot become verified savings.
- Routing is advice only. Repository writes, branches, pull requests, and merges remain disabled.
- Fixture prices and fixture savings are not production price or production savings claims.

## Data-driven architecture

- `registry/models`: model identity, aliases, lifecycle, context limits, and capabilities
- `registry/pricing`: effective-dated price rules and immutable per-event snapshots
- `registry/providers`: provider-to-adapter mapping
- `costdoctor/adapters.py`: Generic, OpenAI, Anthropic, Gemini, Agnes, and Ollama offline normalization
- `costdoctor/evidence.py`: canonical events and append-only receipt chains
- `costdoctor/detectors.py`: measured waste signals across calls, context, retry, cache, tools, agents, and infrastructure
- `costdoctor/benchmark.py`: bound Before/After metrics and quality gate
- `costdoctor/validator.py`: separate price, binding, digest, rollback, and savings recomputation
- `costdoctor/user_report.py`: deterministic 10-second, 1-minute, HTML, and print-friendly user reports
- `costdoctor/report_validator.py`: independent report fact, rendering parity, determinism, and leak validation
- `costdoctor/context_optimizer.py`: deterministic Fact/Authority/Delta/Evidence-pointer selection with a required-fact loss guard
- `costdoctor/capsules.py`: Task, State, Context, Evidence, Delta, and Usage capsule contracts
- `costdoctor/request_adapters.py`: bounded request envelopes for general LLM/API providers; it never performs a network call
- `costdoctor/coding_agents.py`: Registry-driven minimal packets for Codex, Claude Code, and other coding agents
- `costdoctor/measurement.py`: provider usage, exact tokenizer, available tool usage, byte proxy, and unknown measurement grades
- `costdoctor/three_stage.py`: identical-workload RAW → ENGINE → ENGINE+CostDoctor measurement with optimizer overhead
- `costdoctor/three_stage_validator.py`: separate three-stage cost, identity, quality, grade, rollback, and False-PASS recomputation
- `costdoctor/cost_router.py`: rule/local/low-cost/high-model advice ordered by measured cost per successful workload

Adding a conventional new model requires Registry data, not a model-name branch in core code. A new billing dimension, protocol, or capability class may require a versioned contract extension.

## Measurement grades and current OpenAI usage

The engine keeps measurement types separate. `PROVIDER_REPORTED_USAGE` requires a provider response identifier and provider-response/export provenance. `EXACT_TOKENIZER` requires an identified tokenizer. Coding-tool counters are `AVAILABLE_TOOL_USAGE`; byte or arithmetic estimates are `BYTE_PROXY`; missing provenance is `UNKNOWN`. A self-declared `provider_reported: true` flag alone is never enough.

The OpenAI adapter accepts both legacy prompt/completion counters and current Responses usage fields: input tokens, cached/cache-write input details, output tokens, and reasoning-token output details. Output and reasoning are split before pricing to avoid double counting. Model names and prices remain Registry data.

## Universal context and coding-agent packets

`optimize_context()` resolves the latest authority row, converts large evidence to hash/count/locator pointers, selects required facts first, applies a per-call budget, and fails if a required fact cannot fit. The same state produces the same capsule fingerprint. Byte reduction stays a byte-only claim unless an identified tokenizer or provider usage receipt is supplied.

Coding-agent profiles live in `registry/agents`; the core packet builder does not embed a repository or full session. It sends the task, current state, selected context, evidence pointers, delta, repo map metadata, and an explicit selective-read list. A new coding tool normally needs one Registry profile, not a new context core.

## Three-stage benchmark

Run the two public fixture workloads twice and compare their semantic receipts:

```bash
python3 universal/scripts/run_optimizer_acceptance.py --output /tmp/optimizer-a --run-label a
python3 universal/scripts/run_optimizer_acceptance.py --output /tmp/optimizer-b --run-label b
python3 universal/scripts/compare_optimizer_runs.py /tmp/optimizer-a /tmp/optimizer-b --output /tmp/optimizer-fresh.json
```

Each run performs identical-model RAW, ENGINE, and ENGINE+CostDoctor phases; per-item quality checking; strategy rollback; baseline rerun; improvement reapply; independent cost recomputation; and adversarial False-PASS probes. Fixture output is explicitly `BYTE_PROXY` with an unverified fixture price and is not provider billing or a production savings claim. An actual provider claim remains blocked until a sanitized provider usage receipt, matching effective price Evidence, and the user's spend authorization are present. An actual coding-agent efficiency claim likewise requires usage counters exposed by that tool.

The independent validator can also be called directly:

```bash
python3 -m costdoctor.cli validate-three-stage --input three_stage.json --output independent.json
```

## Offline usage import

The input is JSON or JSONL containing provider usage metadata, identifiers, timing, and aggregate counters. It must not contain prompt or response text.

```bash
python3 -m costdoctor.cli usage-import \
  --input safe-usage.jsonl \
  --output costdoctor-usage-evidence.json \
  --provider generic \
  --model your-registry-model \
  --workload workload-id \
  --run-id run-id \
  --commit 0123456789012345678901234567890123456789 \
  --environment github-actions-linux \
  --workload-fingerprint 0123456789012345678901234567890123456789012345678901234567890123
```

Run with `PYTHONPATH=universal`, or from an environment that installs the `universal` package path. Exit code `2` means a price was unknown and the claim was safely blocked.

## Actual acceptance and rollback Evidence

The acceptance runner executes two deterministic public-fixture workloads. Each workload performs Before, improvement, After, quality checking, actual strategy rollback, baseline rerun, improvement reapply, rerun, and independent validation. Run it twice into different empty directories and compare the results:

```bash
python3 universal/scripts/run_acceptance.py --output /tmp/costdoctor-run-a
python3 universal/scripts/run_acceptance.py --output /tmp/costdoctor-run-b
python3 universal/scripts/compare_fresh_runs.py /tmp/costdoctor-run-a /tmp/costdoctor-run-b --output /tmp/fresh-rerun.json
```

The `future-model-x` compatibility case is intentionally defined only in `registry/models/future-model-x.v1.json`. Without a matching price row it completes ingest and reporting but returns `UNKNOWN/BLOCKED`. The acceptance runner then adds a temporary Registry price row outside the repository and proves recalculation without changing core code.

Each actual workload also emits `USER_SUMMARY.md`, `EASY_REPORT.html`, `PRINT_REPORT.html`, a normalized user-report record, and an independent report-validation result. The screen and print renderers expose the same recomputed facts, show trust and application state explicitly, and omit internal paths, hashes, raw JSON, source, secrets, and personal data from the default view.

## Verified Savings meaning

`VERIFIED` binds one executed fixture claim to the repository commit, workload and environment fingerprints, exact model/provider, effective price snapshot, event digests, quality result, rollback proof, producer digest, and independent validator digest. It never generalizes that result to a customer production workload.
