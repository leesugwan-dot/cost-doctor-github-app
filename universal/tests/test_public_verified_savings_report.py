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
        return {"findings": [{"rule": "retry", "signal_count": 18}], "savings": {"status": "UNKNOWN"}}

    def _acceptance(self):
        return {"local_verdict": "PASS", "workloads": [{"quality": {"failed_phases": []}}]}

    def _preflight(self, credential=False, confirmation=False):
        return {"credential_present": credential, "execution_confirmation_valid": confirmation, "approved_max_spend_usd": "0.04"}

    def test_static_and_missing_provider_are_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            report = MODULE.build_report(self._static(), self._acceptance(), out, self._preflight(), None, "leesugwan-dot/active-project-reliability-demo")
        self.assertEqual(report["verdict"], "NEEDS_ACTION")
        self.assertEqual(report["trust_level"], "UNKNOWN")
        self.assertEqual(report["provider"]["status"], "BLOCKED")
        self.assertIsNone(report["reported_stages"]["raw"])
        self.assertTrue(report["false_pass_guards"]["static_not_promoted"])
        self.assertEqual(len(report["user_action_queue"]), 1)

    def test_fixture_reference_never_becomes_provider_savings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "repeated").mkdir()
            packet = {"phases": {phase: {"metrics": {"total_cost_usd": "1.000000000", "usage": {"input_tokens": 10, "output_tokens": 1}, "quality_mean": 1.0}} for phase in ("raw", "engine", "engine_costdoctor")}}
            (root / "repeated" / "three_stage.json").write_text(json.dumps(packet), encoding="utf-8")
            report = MODULE.build_report(self._static(), self._acceptance(), root, self._preflight(credential=True), None, "demo")
        self.assertEqual(report["fixture_reference"]["measurement_grade"], "BYTE_PROXY")
        self.assertFalse(report["fixture_reference"]["provider_actual"])
        self.assertEqual(report["provider"]["status"], "BLOCKED")
        self.assertIsNone(report["validation_overhead"]["net_saving_usd"])

    def test_markdown_explains_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = MODULE.build_report(self._static(), self._acceptance(), Path(tmp), self._preflight(), None, "demo")
            markdown = MODULE.render_markdown(report)
        self.assertIn("UNKNOWN", markdown)
        self.assertIn("실제 Provider", markdown)


if __name__ == "__main__":
    unittest.main(verbosity=2)
