from __future__ import annotations

from typing import Any


DEFAULT_FEATURE_FLAGS = {
    "verified_fix_prepare": False,
    "publish_branch_or_pr": False,
    "automatic_merge": False,
}


def prepare_verified_fix_plan(diagnosis_digest: str, rollback_digest: str, feature_flags: dict[str, bool] | None = None) -> dict[str, Any]:
    flags = {**DEFAULT_FEATURE_FLAGS, **(feature_flags or {})}
    if flags["publish_branch_or_pr"] or flags["automatic_merge"]:
        raise PermissionError("PUBLIC_WRITE_FEATURE_DISABLED")
    return {
        "schema": "costdoctor.verified-fix-plan.v3",
        "status": "PREPARATION_ONLY_FEATURE_FLAG_OFF",
        "diagnosis_digest": diagnosis_digest,
        "rollback_digest": rollback_digest,
        "stages": ["diagnose", "isolated_patch", "before_after", "quality", "rollback_bundle"],
        "branch_or_pr_created": False,
        "merge_performed": False,
        "repository_write": False,
        "feature_flags": flags,
    }
