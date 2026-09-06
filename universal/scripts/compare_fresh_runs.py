from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads((path / "acceptance_summary.json").read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two separate fresh CostDoctor acceptance runs.")
    parser.add_argument("run_a", type=Path)
    parser.add_argument("run_b", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    first = load(args.run_a)
    second = load(args.run_b)
    first_workloads = {item["workload_id"]: item for item in first["workloads"]}
    second_workloads = {item["workload_id"]: item for item in second["workloads"]}
    checks = {
        "different_run_directories": args.run_a.resolve() != args.run_b.resolve(),
        "both_fresh_actual_pass": first.get("verdict") == second.get("verdict") == "PASS",
        "same_commit_binding": first.get("repository_commit") == second.get("repository_commit"),
        "same_environment_binding": first.get("environment_fingerprint") == second.get("environment_fingerprint"),
        "same_workload_set": set(first_workloads) == set(second_workloads),
        "stable_before_metrics": all(
            first_workloads[key]["before_metrics_fingerprint"]
            == second_workloads.get(key, {}).get("before_metrics_fingerprint")
            for key in first_workloads
        ),
        "stable_after_metrics": all(
            first_workloads[key]["after_metrics_fingerprint"]
            == second_workloads.get(key, {}).get("after_metrics_fingerprint")
            for key in first_workloads
        ),
        "stable_verified_savings": all(
            first_workloads[key]["verified_savings_usd"]
            == second_workloads.get(key, {}).get("verified_savings_usd")
            for key in first_workloads
        ),
        "stable_user_report_facts": all(
            first_workloads[key]["user_report_facts_digest"]
            == second_workloads.get(key, {}).get("user_report_facts_digest")
            for key in first_workloads
        ),
        "all_user_reports_validated": all(
            first_workloads[key]["user_report_independent_validation"]
            == second_workloads.get(key, {}).get("user_report_independent_validation")
            == "PASS"
            for key in first_workloads
        ),
        "future_model_pass_both_runs": first["future_model"]["verdict"] == second["future_model"]["verdict"] == "PASS",
        "future_model_report_stable": first["future_model"]["user_report_facts_digest"]
        == second["future_model"]["user_report_facts_digest"],
    }
    result = {
        "schema": "costdoctor.fresh-independent-rerun.v1",
        "run_a_digest": first["summary_digest"],
        "run_b_digest": second["summary_digest"],
        "checks": checks,
        "verdict": "PASS" if all(checks.values()) else "FAIL",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
