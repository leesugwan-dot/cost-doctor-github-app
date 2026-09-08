---
title: LLM cost optimization: start with evidence
description: Evidence-first guidance for reducing LLM cost without confusing static signals with provider usage.
---

# LLM cost optimization: start with evidence

CostDoctor separates a static signal from a measured bill. A repository scan can point to repeated context, retries, model calls, or missing limits, but it cannot prove runtime volume or savings on its own.

## A safe sequence

1. Identify the runtime call path and its production boundary.
2. Capture provider usage for the same workload before changing code.
3. Apply a reversible change in an isolated workspace.
4. Re-run the same workload and compare input, cached, output, retry, quality, and total cost.
5. Keep the change only when quality does not regress and verification overhead is included.

The free Public Scan performs none of the provider calls. It reports a concrete next measurement instead of inventing a percentage; without provider evidence, savings remain `UNKNOWN`.

[Run a free Quick Scan](https://leesugwan-dot.github.io/cost-doctor-github-app/) · [Read the Public Scan boundary](../PUBLIC_SCAN.md)
