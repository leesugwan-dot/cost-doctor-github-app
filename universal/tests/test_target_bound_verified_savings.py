import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


REPORT = load("target_report", ROOT / "universal" / "scripts" / "build_public_verified_savings_report.py")
PRECHECK = load("target_precheck", ROOT / "universal" / "scripts" / "run_target_bound_precheck.py")


class TargetBoundSavingsTests(unittest.TestCase):
    def _acceptance(self):
        return {"local_verdict": "PASS", "workloads": [{"quality": {"failed_phases": []}}]}

    def _binding(self, counts=None, fingerprint="target-fp"):
        return {"target_repository": "owner/target", "target_ref": "main", "target_commit": "abc123", "target_fingerprint": fingerprint, "provider_contract": dict(REPORT.EXPECTED), "static_precheck": {"aggregate_counts": counts or {"files": 4, "retry_signals": 2, "cache_signals": 1, "model_call_signals": 3}}, "workload": {"ready": False, "reason": "TARGET_WORKLOAD_DESCRIPTOR_REQUIRED"}}

    def test_static_counts_are_target_derived_not_fixture_or_literal(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = REPORT.build_report({"findings": [{"rule": "retry", "signal_count": 53}]}, self._acceptance(), Path(tmp), {"credential_present": False, "approved_max_spend_usd": "0.04"}, None, target_binding=self._binding({"files": 7, "retry_signals": 1, "cache_signals": 0, "model_call_signals": 2}))
        self.assertEqual(report["static_precheck"]["signal_counts"]["files"], 7)
        self.assertNotEqual(report["static_precheck"]["signal_counts"]["files"], 53)
        self.assertNotIn("active_project", report)

    def test_missing_target_secret_requests_only_upstage(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = REPORT.build_report({"findings": []}, self._acceptance(), Path(tmp), {"credential_present": False, "credential_source": "UNVERIFIED_OR_ABSENT", "approved_max_spend_usd": "0.04"}, None, target_binding=self._binding())
        self.assertEqual(len(report["user_action_queue"]), 1)
        self.assertEqual(report["user_action_queue"][0]["secret_name"], "UPSTAGE_API_KEY")
        self.assertNotIn("OPENAI_API_KEY", json.dumps(report, ensure_ascii=False))

    def test_openai_fixture_result_cannot_bind_to_target(self):
        result = {"provider": "openai", "model": "gpt-5.6-luna", "target_repository": "owner/target", "target_binding_fingerprint": "target-fp", "provider_authenticated_verdict": "PASS", "pricing_status": "PROVIDER_PUBLISHED"}
        with tempfile.TemporaryDirectory() as tmp:
            report = REPORT.build_report({"findings": []}, self._acceptance(), Path(tmp), {"credential_present": True, "credential_source": "TARGET_REPOSITORY_GITHUB_SECRET"}, result, target_binding=self._binding())
        self.assertEqual(report["provider"]["status"], "BLOCKED")
        self.assertEqual(report["provider"]["verdict"], "TARGET_BINDING_MISMATCH")
        self.assertFalse(report["false_pass_guards"]["openai_fixture_not_target"] is False)

    def test_workload_descriptor_is_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".costdoctor").mkdir()
            (repo / ".costdoctor" / "target-workload.json").write_text(json.dumps({"kind": "expense", "items": [{"prompt": "private", "expected": "ok"}]}), encoding="utf-8")
            descriptor = PRECHECK.workload_descriptor(repo)
        self.assertTrue(descriptor["ready"])
        self.assertEqual(descriptor["item_count"], 1)
        self.assertNotIn("private", json.dumps(descriptor))


if __name__ == "__main__":
    unittest.main()
