---
title: What static analysis can and cannot prove
description: What a read-only repository scan can establish and what still needs runtime evidence.
---

# What static analysis can and cannot prove

Static analysis is valuable for prioritizing review. It can locate likely call paths, repeated context construction, retry configuration, cache-shaped code, and token-limit settings without running customer code.

It cannot prove request volume, provider billing, hidden framework context, quality, or a verified saving percentage. The public path therefore keeps four states separate: structural diagnosis, deterministic measurement, actual usage, and verified savings. A missing secret is a normal free-scan state, not a reason to fabricate a number; savings remain `UNKNOWN` until evidence exists.

[Run a free Quick Scan](https://leesugwan-dot.github.io/cost-doctor-github-app/) · [Private Self-Scan](../PRIVATE_REPO_SELF_SCAN.md)
