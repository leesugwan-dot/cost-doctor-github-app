from __future__ import annotations

from statistics import mean
from typing import Any, Iterable


def evaluate_quality(
    before_scores: Iterable[float] | None,
    after_scores: Iterable[float] | None,
    threshold: float,
    allowed_regression: float = 0.0,
) -> dict[str, Any]:
    before = list(before_scores or [])
    after = list(after_scores or [])
    if not before or not after:
        return {"verdict": "NEEDS_EVIDENCE", "reason": "QUALITY_EVIDENCE_MISSING"}
    before_mean = mean(before)
    after_mean = mean(after)
    if after_mean < threshold:
        verdict = "FAIL"
        reason = "QUALITY_THRESHOLD_NOT_MET"
    elif after_mean + allowed_regression < before_mean:
        verdict = "FAIL"
        reason = "QUALITY_REGRESSION"
    else:
        verdict = "PASS"
        reason = "QUALITY_MAINTAINED_OR_IMPROVED"
    return {
        "verdict": verdict,
        "reason": reason,
        "metric": "deterministic_task_score",
        "before_mean": round(before_mean, 9),
        "after_mean": round(after_mean, 9),
        "threshold": threshold,
        "allowed_regression": allowed_regression,
        "before_samples": len(before),
        "after_samples": len(after),
    }
