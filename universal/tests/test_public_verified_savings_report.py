import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "universal" / "scripts" / "build_public_verified_savings_report.py"
SPEC = importlib.util.spec_from_file_location("public_verified_report", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PublicVerifiedSavingsReportTests(unittest.TestCase):
    def _static(self):
        return {"findings": [{"rule": "RETRY_LOOP", "signal_count": 18}, {"rule": "CACHE_SIGNAL", "signal_count": 6}], "savings": {"status": "UNKNOWN"}}

    def _acceptance(self):
        return {"local_verdict": "PASS", "workloads": [{"quality": {"failed_phases": []}}]}

    def _binding(self):
        return {"target_repository": "owner/repository", "target_ref": "main", "target_commit": "abc123", "target_fingerprint": "target-fp", "provider_contract": {"provider": "anthropic", "adapter": "anthropic_v1", "model": "claude-test", "credential_name": "ANTHROPIC_API_KEY", "base_url": "https://api.anthropic.com"}, "static_precheck": {"aggregate_counts": {"files": 10, "retry_signals": 18, "cache_signals": 6, "model_call_signals": 4}}, "workload": {"ready": False, "reason": "DESCRIPTOR_OPTIONAL_FOR_STAGE2"}}

    def test_static_and_missing_provider_still_produce_stage2(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = MODULE.build_report(self._static(), self._acceptance(), Path(tmp), {"credential_present": False, "approved_max_spend_usd": "0.04"}, None, target_binding=self._binding())
        self.assertEqual(report["verdict"], "STRUCTURAL_DIAGNOSIS")
        self.assertEqual(report["trust_level"], "L1_STRUCTURAL_DIAGNOSIS")
        self.assertEqual(report["provider"]["status"], "OPTIONAL_NOT_CONFIGURED")
        self.assertGreaterEqual(len(report["stage2_diagnosis"]["findings"]), 2)
        self.assertEqual(report["user_action_queue"], [])

    def test_fixture_reference_never_becomes_provider_savings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "repeated").mkdir()
            packet = {"phases": {phase: {"metrics": {"total_cost_usd": "1.000000000", "usage": {"input_tokens": 10, "output_tokens": 1}, "quality_mean": 1.0}} for phase in MODULE.PHASES}}
            (root / "repeated" / "three_stage.json").write_text(json.dumps(packet), encoding="utf-8")
            report = MODULE.build_report(self._static(), self._acceptance(), root, {"credential_present": False}, None, target_binding=self._binding())
        self.assertEqual(report["fixture_reference"]["measurement_grade"], "BYTE_PROXY")
        self.assertFalse(report["fixture_reference"]["provider_actual"])
        self.assertEqual(report["provider"]["status"], "OPTIONAL_NOT_CONFIGURED")
        self.assertIsNone(report["validation_overhead"]["net_saving_usd"])

    def test_markdown_explains_structural_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = MODULE.build_report(self._static(), self._acceptance(), Path(tmp), {"credential_present": False}, None, target_binding=self._binding())
            markdown = MODULE.render_markdown(report)
        self.assertIn("STRUCTURAL_DIAGNOSIS", markdown)
        self.assertIn("예상 효과", markdown)
        self.assertIn("Provider Secret이 없어도", markdown)


if __name__ == "__main__":
    unittest.main(verbosity=2)
