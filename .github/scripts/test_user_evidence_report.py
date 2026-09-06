#!/usr/bin/env python3

import importlib.util
import json
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("user_evidence_report.py")
SPEC = importlib.util.spec_from_file_location("user_evidence_report", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class UserEvidenceReportTests(unittest.TestCase):
    def setUp(self):
        self.repo = {
            "full_name": "leesugwan-dot/cost-doctor-github-app",
            "stargazers_count": 4,
            "forks_count": 2,
        }

    def test_aggregate_counts_exclude_owner_bots_and_pull_requests(self):
        issues = [
            {"title": "[CostDoctor Scan] repo", "user": {"login": "external-one"}},
            {"title": "[CostDoctor Scan] again", "user": {"login": "external-one"}},
            {"title": "[CostDoctor Feedback] helpful", "user": {"login": "external-two"}},
            {"title": "[CostDoctor Scan] owner", "user": {"login": "leesugwan-dot"}},
            {"title": "[CostDoctor Scan] bot", "user": {"login": "dependabot[bot]"}},
            {"title": "[CostDoctor Scan] pr", "user": {"login": "external-three"}, "pull_request": {}},
        ]
        runs = [
            {"conclusion": "success", "actor": {"login": "external-one"}},
            {"conclusion": "failure", "actor": {"login": "external-two"}},
            {"conclusion": "success", "actor": {"login": "leesugwan-dot"}},
        ]
        report = MODULE.build_report(self.repo, issues, runs, "leesugwan-dot", "2026-09-06T00:00:00+00:00")
        signals = report["signals"]
        self.assertEqual(signals["external_scan_requests_total"], 2)
        self.assertEqual(signals["external_scan_requesters_unique"], 1)
        self.assertEqual(signals["successful_external_scan_runs_total"], 1)
        self.assertEqual(signals["external_feedback_issues_total"], 1)
        self.assertTrue(report["external_interest_detected"])
        self.assertTrue(report["confirmed_public_scan_usage_detected"])

    def test_outputs_never_contain_usernames(self):
        secret_login = "private-looking-user-name"
        secret_body = "private-looking-issue-body"
        issues = [{"title": "[CostDoctor Scan] repo", "body": secret_body, "user": {"login": secret_login}}]
        runs = [{"conclusion": "success", "actor": {"login": secret_login}}]
        report = MODULE.build_report(self.repo, issues, runs, "leesugwan-dot", "2026-09-06T00:00:00+00:00")
        serialized = json.dumps(report, ensure_ascii=False) + MODULE.render_markdown(report) + MODULE.marker(report)
        self.assertNotIn(secret_login, serialized)
        self.assertNotIn(secret_body, serialized)
        self.assertFalse(report["privacy"]["usernames_output"])
        self.assertFalse(report["privacy"]["user_issue_bodies_or_comments_output"])
        self.assertTrue(report["privacy"]["tracking_issue_marker_read"])
        self.assertFalse(report["privacy"]["customer_source_or_filenames_read"])
        self.assertFalse(report["privacy"]["external_telemetry"])

    def test_notification_requires_new_external_evidence(self):
        empty = MODULE.build_report(self.repo, [], [], "leesugwan-dot", "2026-09-06T00:00:00+00:00")
        self.assertFalse(MODULE.has_new_evidence(empty, None))

        issues = [{"title": "[CostDoctor Feedback] useful", "user": {"login": "external"}}]
        report = MODULE.build_report(self.repo, issues, [], "leesugwan-dot", "2026-09-06T00:00:00+00:00")
        self.assertTrue(MODULE.has_new_evidence(report, None))
        previous = MODULE.parse_marker(MODULE.marker(report))
        self.assertFalse(MODULE.has_new_evidence(report, previous))


if __name__ == "__main__":
    unittest.main()
