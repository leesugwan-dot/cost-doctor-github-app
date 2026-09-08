---
title: Token and context cost
description: Measure token and context changes without claiming bytes are tokens.
---

# Token and context cost

Bytes are not tokens. A deterministic estimate is useful only when its input, tokenizer, and measurement universe are recorded. A valid Before/After/Delta relationship must satisfy:

```text
0 <= delta <= before
optimized >= 0
before - optimized == delta
```

If those invariants cannot be proven, the report hides the numeric savings card and keeps an evidence downgrade, so savings remain `UNKNOWN`. Provider usage, when available, remains the highest-confidence source for input, cached, output, and reasoning tokens.

[Run a free Quick Scan](https://leesugwan-dot.github.io/cost-doctor-github-app/)
