#!/usr/bin/env python3

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class DiscoveryContractTests(unittest.TestCase):
    def text(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_marketplace_metadata_and_conversion_path(self):
        action = self.text("action.yml")
        readme = self.text("README.md")
        self.assertIn("CostDoctor AI Cost & Token Review", action)
        self.assertIn("AI/LLM API cost review", action)
        self.assertIn("Cost Doctor", action)
        self.assertIn("using: node24", action)
        self.assertIn("main: costdoctor-entry/entry/action.mjs", action)
        description = next(line.split(":", 1)[1].strip() for line in action.splitlines() if line.startswith("description:"))
        self.assertLessEqual(len(description), 125)
        self.assertIn("Free AI/LLM API Cost Review for GitHub", readme)
        self.assertIn("leesugwan-dot/cost-doctor-github-app@v1.0.1", readme)
        self.assertIn("issues/new?template=public-scan.yml", readme)
        self.assertIn("issues/new?template=feedback.yml", readme)

    def test_reporting_is_repo_native_aggregate_and_bounded(self):
        workflow = self.text(".github/workflows/user-evidence-report.yml")
        script = self.text(".github/scripts/user_evidence_report.py")
        self.assertIn("workflow_run:", workflow)
        self.assertIn("schedule:", workflow)
        self.assertIn("actions: read", workflow)
        self.assertIn("issues: write", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("pull_request_target", workflow)
        self.assertNotIn("secrets.", workflow)
        self.assertIn("github.token", workflow)
        self.assertIn('API_ROOT = "https://api.github.com"', script)
        self.assertIn("MAX_PAGES", script)
        self.assertIn('"aggregate_counts_only": True', script)
        self.assertIn('"usernames_output": False', script)
        self.assertIn('"user_issue_bodies_or_comments_output": False', script)
        self.assertIn('"external_telemetry": False', script)

    def test_existing_safety_boundaries_are_not_downgraded(self):
        private_workflow = self.text("costdoctor-entry/private-repo-selfscan.yml")
        readiness = json.loads(self.text("product_readiness.json"))
        measured = json.loads(self.text("measured_run_contract.json"))
        self.assertIn("contents: read", private_workflow)
        self.assertNotIn("contents: write", private_workflow)
        self.assertFalse(readiness["hard_boundaries"]["operator_personal_pc_for_customer_code"])
        self.assertFalse(readiness["hard_boundaries"]["public_scan_target_repository_write"])
        self.assertEqual(readiness["deferred_decisions"]["D5_automatic_code_modification_and_pr"], "DEFERRED_UNTIL_PUBLIC_REACTION")
        self.assertEqual(readiness["deferred_decisions"]["D7_monetization_model_and_price"], "DEFERRED_UNTIL_PUBLIC_REACTION")
        self.assertEqual(readiness["deferred_decisions"]["D9_ai_auto_fix_provider_and_code_transfer"], "DEFERRED_UNTIL_PUBLIC_REACTION")
        self.assertTrue(measured["customer_controls"]["per_run_budget_approval_required"])
        self.assertTrue(measured["budget_guard"]["fail_closed"])

    def test_feedback_form_warns_against_sensitive_input(self):
        form = self.text(".github/ISSUE_TEMPLATE/feedback.yml")
        self.assertIn("[CostDoctor Feedback]", form)
        self.assertIn("API key", form)
        self.assertIn("Secret", form)
        self.assertIn("개인정보", form)
        self.assertIn("required: true", form)


if __name__ == "__main__":
    unittest.main()
