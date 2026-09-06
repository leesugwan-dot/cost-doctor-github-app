from __future__ import annotations

import re
from pathlib import Path
from typing import Any


PIN_RE = re.compile(r"^\s*uses:\s*[^\s]+@([0-9a-f]{40})(?:\s|$)", re.MULTILINE)


def inspect_github_boundaries(repository: Path) -> dict[str, Any]:
    private = (repository / "costdoctor-entry/private-repo-selfscan.yml").read_text(encoding="utf-8")
    public = (repository / ".github/workflows/public-scan.yml").read_text(encoding="utf-8")
    root_action = (repository / "action.yml").read_text(encoding="utf-8")
    workflow_files = sorted((repository / ".github/workflows").glob("*.yml"))
    all_workflows = "\n".join(path.read_text(encoding="utf-8") for path in workflow_files)
    uses_lines = [line for line in all_workflows.splitlines() if line.strip().startswith("uses:")]
    unpinned = [line.strip().split("uses:", 1)[1].strip() for line in uses_lines if not PIN_RE.match(line) and not line.strip().endswith("uses: ./") and "uses: ./" not in line]
    checks = {
        "root_action_name_preserved": root_action.startswith("name: CostDoctor Repository Review\n"),
        "root_action_node24": "using: node24" in root_action,
        "private_contents_read": "contents: read" in private,
        "private_contents_write_absent": "contents: write" not in private,
        "public_contents_write_absent": "contents: write" not in public,
        "public_pull_request_target_absent": "pull_request_target" not in public,
        "private_persist_credentials_false": "persist-credentials: false" in private,
        "workflow_external_actions_pinned": not unpinned,
        "workflow_secret_literal_absent": "sk-" not in all_workflows and "github_pat_" not in all_workflows,
    }
    return {
        "schema": "costdoctor.github-guard.v1",
        "verdict": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "unpinned_external_actions": unpinned,
        "workflow_count": len(workflow_files),
        "github_app_adapter": {
            "status": "SEPARATE_DISABLED_PREPARATION_ONLY",
            "activation_requirements": [
                "webhook_signature_verification",
                "delivery_id_deduplication",
                "replay_window",
                "installation_repository_binding",
                "minimum_permissions",
                "read_only_diagnostics_first",
            ],
        },
        "runner_support_status": "REPOSITORY_CONFIG_ONLY_NOT_EXTERNALLY_ASSERTED",
    }
