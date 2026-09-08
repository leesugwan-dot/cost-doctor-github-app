---
title: Prompt caching and context reuse
description: Evidence boundaries for provider prompt caching and repeated context.
---

# Prompt caching and context reuse

Provider prompt caching is different from a general file cache, build cache, or memoization of a local function. Only provider usage can confirm cached input, cache writes, cache reads, and their price treatment.

Static review can still identify repeated request construction and show a safe symbol or call group to inspect. It should not claim saved tokens until the same workload reports before/after input and cached usage. A cache that increases misses, invalidation, or storage work is not automatically a saving; without that evidence, savings remain `UNKNOWN`.

[Run a free Quick Scan](https://leesugwan-dot.github.io/cost-doctor-github-app/) · [Read the evidence boundary](../PUBLIC_SCAN.md)
