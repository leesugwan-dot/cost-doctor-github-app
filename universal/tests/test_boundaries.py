from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "universal"))

from costdoctor.compat import read_report  # noqa: E402
from costdoctor.detectors import DETECTOR_IDS, detect_waste  # noqa: E402
from costdoctor.github_guard import inspect_github_boundaries  # noqa: E402
from costdoctor.registry import ModelRegistry  # noqa: E402
from costdoctor.verified_fix import prepare_verified_fix_plan  # noqa: E402


class BoundaryTests(unittest.TestCase):
    def test_existing_github_boundaries_pass(self):
        self.assertEqual(inspect_github_boundaries(ROOT)["verdict"], "PASS")

    def test_marketplace_identity_is_preserved(self):
        action = (ROOT / "action.yml").read_text(encoding="utf-8")
        self.assertTrue(action.startswith("name: CostDoctor Repository Review\n"))
        self.assertIn("using: node24", action)

    def test_private_self_scan_remains_read_only(self):
        workflow = (ROOT / "costdoctor-entry" / "private-repo-selfscan.yml").read_text(encoding="utf-8")
        self.assertIn("contents: read", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertIn("persist-credentials: false", workflow)

    def test_public_scan_has_no_target_write(self):
        workflow = (ROOT / ".github" / "workflows" / "public-scan.yml").read_text(encoding="utf-8")
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("pull_request_target", workflow)

    def test_legacy_report_unknown_fields_are_preserved(self):
        old = {"schema": "costdoctor.repository-entry.v1", "verdict": "SCAN_COMPLETE", "future": 7}
        envelope = read_report(old)
        self.assertEqual(envelope["legacy_report"]["future"], 7)
        self.assertEqual(envelope["compatibility"], "BACKWARD_COMPATIBLE_V1")

    def test_unknown_schema_is_preserved(self):
        envelope = read_report({"schema": "future.schema", "new": True})
        self.assertEqual(envelope["legacy_report"]["new"], True)
        self.assertEqual(envelope["compatibility"], "UNKNOWN_FIELDS_PRESERVED")

    def test_verified_fix_defaults_to_no_write(self):
        plan = prepare_verified_fix_plan("a" * 64, "b" * 64)
        self.assertFalse(plan["repository_write"])
        self.assertFalse(plan["merge_performed"])

    def test_verified_fix_public_pr_is_blocked(self):
        with self.assertRaisesRegex(PermissionError, "PUBLIC_WRITE_FEATURE_DISABLED"):
            prepare_verified_fix_plan("a", "b", {"publish_branch_or_pr": True})

    def test_future_model_literal_is_absent_from_core(self):
        core = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "universal" / "costdoctor").glob("*.py"))
        self.assertNotIn("future-model-x", core)

    def test_core_has_no_network_client_imports(self):
        core = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "universal" / "costdoctor").glob("*.py"))
        for token in ("import requests", "import urllib", "import httpx", "import socket"):
            self.assertNotIn(token, core)

    def test_registry_jsons_parse(self):
        for path in (ROOT / "universal" / "registry").rglob("*.json"):
            self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)

    def test_detector_reports_risk_and_rollback(self):
        event = {
            "input_fingerprint": "same",
            "context_fingerprint": "same-context",
            "success": True,
            "usage": {"input_tokens": 1000, "output_tokens": 10, "retry_count": 1, "tool_calls": 0, "reasoning_tokens": 0},
            "latency_ms": 1,
            "cache_hit": False,
            "metadata": {"full_history_reinjected": True, "summary_used": False, "conversation_turns": 20, "cache_eligible": True, "required_capability_score": 1, "local_compute_eligible": True, "parallelizable": True, "executed_serially": True, "batch_eligible": True},
            "model": "fixture-pro-v1",
            "batch": False,
        }
        findings = detect_waste([event, dict(event)], ModelRegistry(ROOT / "universal" / "registry" / "models"))
        self.assertGreaterEqual(len(findings), 8)
        self.assertTrue(all(item["risk"] and item["rollback"] and item["verified_savings_usd"] is None for item in findings))

    def test_detector_catalog_covers_full_workspec_matrix(self):
        required = {
            "duplicate_call", "identical_input_repeat", "overqualified_model", "simple_task_expensive_model",
            "excessive_reasoning", "fallback_chain_excess", "model_switch_rework", "oversized_context",
            "repeated_prefix", "full_history_reinjection", "duplicate_retrieval", "low_relevance_rag",
            "excessive_output_limit", "inefficient_chunk_size", "summary_missing", "excessive_retry",
            "same_error_retry", "retry_backoff_invalid", "full_reexecution_after_failure", "timeout_duplicate",
            "idempotency_missing", "cache_missing", "low_cache_hit_rate", "cache_ttl_mismatch",
            "cache_scope_unsafe", "cache_cost_exceeds_saving", "repeated_tool_loop",
            "planner_reviewer_duplication", "multi_agent_duplicate", "repeated_fetch",
            "large_tool_output_reinjection", "model_used_for_local_compute", "serial_parallelizable_calls",
            "batch_opportunity", "concurrency_retry_amplification", "queue_duplicate_execution",
            "model_occupied_while_waiting", "failure_cost_spike", "latency_spike", "tool_rework_cost",
        }
        self.assertTrue(required.issubset(set(DETECTOR_IDS)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
