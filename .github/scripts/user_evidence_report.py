#!/usr/bin/env python3
"""Build and optionally notify privacy-safe CostDoctor user Evidence.

Only aggregate metadata from this public repository is reported. Usernames are
used in memory for de-duplication and are never written to outputs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_ROOT = "https://api.github.com"
SCAN_TITLE_PREFIX = "[CostDoctor Scan]"
FEEDBACK_TITLE_PREFIX = "[CostDoctor Feedback]"
REPORT_ISSUE_TITLE = "[CostDoctor User Evidence] External usage detected"
MARKER_RE = re.compile(r"<!-- costdoctor-user-evidence:(\{.*?\}) -->", re.DOTALL)
MAX_PAGES = 5


def _login(item: dict[str, Any] | None) -> str:
    if not item:
        return ""
    return str(item.get("login") or "").strip().lower()


def _is_external(login: str, owner: str) -> bool:
    normalized = login.strip().lower()
    return bool(normalized and normalized != owner.strip().lower() and not normalized.endswith("[bot]"))


def _external_issue_actors(
    issues: list[dict[str, Any]], owner: str, prefix: str
) -> list[str]:
    actors: list[str] = []
    for issue in issues:
        if "pull_request" in issue:
            continue
        if not str(issue.get("title") or "").startswith(prefix):
            continue
        actor = _login(issue.get("user"))
        if _is_external(actor, owner):
            actors.append(actor)
    return actors


def build_report(
    repo_meta: dict[str, Any],
    issues: list[dict[str, Any]],
    workflow_runs: list[dict[str, Any]],
    owner: str,
    observed_at: str | None = None,
) -> dict[str, Any]:
    scan_actors = _external_issue_actors(issues, owner, SCAN_TITLE_PREFIX)
    feedback_actors = _external_issue_actors(issues, owner, FEEDBACK_TITLE_PREFIX)
    successful_run_actors: list[str] = []
    for run in workflow_runs:
        actor = _login(run.get("actor"))
        if run.get("conclusion") == "success" and _is_external(actor, owner):
            successful_run_actors.append(actor)

    signals = {
        "external_scan_requests_total": len(scan_actors),
        "external_scan_requesters_unique": len(set(scan_actors)),
        "successful_external_scan_runs_total": len(successful_run_actors),
        "successful_external_scan_users_unique": len(set(successful_run_actors)),
        "external_feedback_issues_total": len(feedback_actors),
        "external_feedback_authors_unique": len(set(feedback_actors)),
        "repository_stars": int(repo_meta.get("stargazers_count") or 0),
        "repository_forks": int(repo_meta.get("forks_count") or 0),
    }
    external_interest = any(
        signals[key] > 0
        for key in (
            "external_scan_requests_total",
            "successful_external_scan_runs_total",
            "external_feedback_issues_total",
        )
    )
    confirmed_usage = signals["successful_external_scan_runs_total"] > 0
    return {
        "schema": "costdoctor.user-evidence-report.v1",
        "observed_at": observed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "repository": str(repo_meta.get("full_name") or ""),
        "external_interest_detected": external_interest,
        "confirmed_public_scan_usage_detected": confirmed_usage,
        "signals": signals,
        "unavailable_by_design": {
            "marketplace_install_count": "UNKNOWN_NOT_EXPOSED",
            "private_self_scan_usage": "UNKNOWN_TELEMETRY_OFF",
            "verified_cost_savings": "UNKNOWN_WITHOUT_MEASURED_EVIDENCE",
        },
        "privacy": {
            "aggregate_counts_only": True,
            "usernames_output": False,
            "user_issue_bodies_or_comments_output": False,
            "tracking_issue_marker_read": True,
            "customer_source_or_filenames_read": False,
            "private_repository_activity_read": False,
            "external_telemetry": False,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    s = report["signals"]
    usage = "DETECTED" if report["confirmed_public_scan_usage_detected"] else "NOT_YET_DETECTED"
    interest = "DETECTED" if report["external_interest_detected"] else "NOT_YET_DETECTED"
    return f"""# CostDoctor user Evidence report

- Observed: `{report['observed_at']}`
- External interest: **{interest}**
- Confirmed successful public-scan usage: **{usage}**

| Aggregate signal | Count |
| --- | ---: |
| External public-scan requests | {s['external_scan_requests_total']} |
| Unique external public-scan requesters | {s['external_scan_requesters_unique']} |
| Successful external public-scan runs | {s['successful_external_scan_runs_total']} |
| Unique successful external public-scan users | {s['successful_external_scan_users_unique']} |
| External feedback Issues | {s['external_feedback_issues_total']} |
| Repository stars (interest only) | {s['repository_stars']} |
| Repository forks (interest only) | {s['repository_forks']} |

Marketplace install count and private Self-Scan usage remain `UNKNOWN` by design. External telemetry is off. This report contains no usernames, user Issue bodies or comments, customer source, filenames, secrets, or private-repository activity. The automation reads only its own tracking-Issue marker so it can report increases once.
"""


def signature(report: dict[str, Any]) -> dict[str, int]:
    keys = (
        "external_scan_requests_total",
        "successful_external_scan_runs_total",
        "external_feedback_issues_total",
    )
    return {key: int(report["signals"][key]) for key in keys}


def marker(report: dict[str, Any]) -> str:
    return "<!-- costdoctor-user-evidence:" + json.dumps(signature(report), sort_keys=True, separators=(",", ":")) + " -->"


def parse_marker(body: str) -> dict[str, int] | None:
    match = MARKER_RE.search(body)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return {str(key): int(value) for key, value in data.items() if isinstance(value, int)}


def has_new_evidence(report: dict[str, Any], previous: dict[str, int] | None) -> bool:
    if not report["external_interest_detected"]:
        return False
    current = signature(report)
    if previous is None:
        return True
    return any(current[key] > int(previous.get(key, 0)) for key in current)


class GitHubAPI:
    def __init__(self, token: str):
        self.token = token

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            API_ROOT + path,
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "costdoctor-user-evidence-report",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=20) as response:
                content = response.read()
        except HTTPError as exc:
            raise RuntimeError(f"GitHub API {method} {path.split('?')[0]} failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"GitHub API {method} {path.split('?')[0]} was unavailable") from exc
        return json.loads(content.decode("utf-8")) if content else None

    def list_issues(self, repository: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for page in range(1, MAX_PAGES + 1):
            query = urlencode({"state": "all", "per_page": 100, "page": page})
            batch = self.request("GET", f"/repos/{repository}/issues?{query}")
            if not isinstance(batch, list):
                raise RuntimeError("GitHub issues response was not a list")
            results.extend(batch)
            if len(batch) < 100:
                break
        return results

    def list_public_scan_runs(self, repository: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for page in range(1, MAX_PAGES + 1):
            query = urlencode({"event": "issues", "status": "completed", "per_page": 100, "page": page})
            data = self.request("GET", f"/repos/{repository}/actions/workflows/public-scan.yml/runs?{query}")
            batch = data.get("workflow_runs") if isinstance(data, dict) else None
            if not isinstance(batch, list):
                raise RuntimeError("GitHub workflow-runs response was not a list")
            results.extend(batch)
            if len(batch) < 100:
                break
        return results


def find_tracking_issue(issues: list[dict[str, Any]]) -> dict[str, Any] | None:
    for issue in issues:
        if "pull_request" not in issue and issue.get("title") == REPORT_ISSUE_TITLE:
            return issue
    return None


def notify(api: GitHubAPI, repository: str, issues: list[dict[str, Any]], report: dict[str, Any]) -> str:
    tracking = find_tracking_issue(issues)
    previous = parse_marker(str(tracking.get("body") or "")) if tracking else None
    if not has_new_evidence(report, previous):
        return "NO_NEW_EXTERNAL_EVIDENCE"

    body = render_markdown(report) + "\n" + marker(report)
    if tracking is None:
        api.request("POST", f"/repos/{repository}/issues", {"title": REPORT_ISSUE_TITLE, "body": body})
        return "CREATED_REPORT_ISSUE"

    number = int(tracking["number"])
    api.request("PATCH", f"/repos/{repository}/issues/{number}", {"body": body})
    api.request(
        "POST",
        f"/repos/{repository}/issues/{number}/comments",
        {"body": "New aggregate external user Evidence was detected.\n\n" + render_markdown(report)},
    )
    return "UPDATED_REPORT_ISSUE"


def write_ci_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def load_fixture(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["repository"], data["issues"], data["workflow_runs"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Create aggregate, privacy-safe CostDoctor user Evidence")
    parser.add_argument("--output-dir", default="user-evidence-output")
    parser.add_argument("--input-fixture")
    parser.add_argument("--observed-at")
    parser.add_argument("--notify", action="store_true")
    args = parser.parse_args()

    repository = os.environ.get("GITHUB_REPOSITORY", "leesugwan-dot/cost-doctor-github-app")
    owner = repository.split("/", 1)[0]
    api: GitHubAPI | None = None
    if args.input_fixture:
        repo_meta, issues, runs = load_fixture(Path(args.input_fixture))
    else:
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            raise RuntimeError("GITHUB_TOKEN is required for live repository-native reporting")
        api = GitHubAPI(token)
        repo_meta = api.request("GET", f"/repos/{repository}")
        issues = api.list_issues(repository)
        runs = api.list_public_scan_runs(repository)

    report = build_report(repo_meta, issues, runs, owner, args.observed_at)
    markdown = render_markdown(report)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "report.md").write_text(markdown, encoding="utf-8")

    notification_action = "NOT_REQUESTED"
    if args.notify:
        if api is None:
            raise RuntimeError("Notification is disabled for fixture input")
        notification_action = notify(api, repository, issues, report)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write(markdown)
            handle.write(f"\nNotification: `{notification_action}`\n")
    write_ci_output("external-interest-detected", str(report["external_interest_detected"]).lower())
    write_ci_output("confirmed-usage-detected", str(report["confirmed_public_scan_usage_detected"]).lower())
    write_ci_output("notification-action", notification_action)
    print(json.dumps({"verdict": "PASS", "notification_action": notification_action}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # fail closed without raw HTTP bodies or secrets
        print(f"CostDoctor user Evidence report failed safely: {exc}", file=sys.stderr)
        raise SystemExit(1)
