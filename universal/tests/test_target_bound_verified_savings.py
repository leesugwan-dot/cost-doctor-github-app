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
DISCOVERY = load("provider_discovery", ROOT / "universal" / "costdoctor" / "provider_discovery.py")


class UniversalStage2Tests(unittest.TestCase):
    def _acceptance(self):
        return {"local_verdict": "PASS", "workloads": [{"quality": {"failed_phases": []}}]}

    def _binding(self, contract=None, counts=None, provider_detection=None):
        return {"target_repository": "owner/target", "target_ref": "main", "target_commit": "abc123", "target_fingerprint": "target-fp", "provider_contract": contract or {"provider": "openai", "adapter": "openai_v1", "model": "gpt-test", "credential_name": "OPENAI_API_KEY", "base_url": "https://api.openai.com/v1"}, "provider_detection": provider_detection or {}, "static_precheck": {"aggregate_counts": counts or {"files": 7, "retry_signals": 2, "cache_signals": 1, "model_call_signals": 3}}, "workload": {"ready": False, "reason": "DESCRIPTOR_OPTIONAL_FOR_STAGE2"}}

    def test_secretless_stage2_returns_diagnosis_not_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = REPORT.build_report({"findings": [{"rule": "RETRY_LOOP", "signal_count": 53}]}, self._acceptance(), Path(tmp), {"credential_present": False, "approved_max_spend_usd": "0.04"}, None, target_binding=self._binding())
        self.assertEqual(report["verdict"], "STRUCTURAL_DIAGNOSIS")
        self.assertEqual(report["trust_level"], "L1_STRUCTURAL_DIAGNOSIS")
        self.assertGreaterEqual(len(report["stage2_diagnosis"]["findings"]), 1)
        self.assertEqual(report["user_action_queue"], [])

    def test_static_counts_are_target_derived_not_fixture_or_literal(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = REPORT.build_report({"findings": [{"rule": "RETRY_LOOP", "signal_count": 53}]}, self._acceptance(), Path(tmp), {"credential_present": False, "approved_max_spend_usd": "0.04"}, None, target_binding=self._binding({"provider": "ollama", "adapter": "ollama_v1", "model": "local-fixture-v1", "credential_name": None, "base_url": "http://localhost:11434/api"}, {"files": 7, "retry_signals": 1, "cache_signals": 0, "model_call_signals": 2}))
        self.assertEqual(report["static_precheck"]["signal_counts"]["files"], 7)
        self.assertNotEqual(report["static_precheck"]["signal_counts"]["files"], 53)
        self.assertTrue(report["false_pass_guards"]["fixture_not_target"])

    def test_provider_detection_is_registry_driven_for_multiple_fixtures(self):
        cases = {
            "openai": "from openai import OpenAI\nclient.responses.create(model='gpt-test')\n",
            "anthropic": "import anthropic\nclient.messages.create(model='claude-test')\n",
            "gemini": "from google import generativeai\nmodel.generateContent('x')\n",
            "upstage": "base_url='https://api.upstage.ai/v1'\nmodel='solar-pro3'\n",
            "ollama": "import ollama\nollama.generate(model='local')\n",
        }
        for expected, text in cases.items():
            with tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp)
                (repo / "app.py").write_text(text, encoding="utf-8")
                result = DISCOVERY.discover(repo, ROOT / "universal" / "registry")
            self.assertEqual(result["status"], "DETECTED", expected)
            self.assertEqual(result["selected"]["provider"], expected, expected)

    def test_unknown_provider_and_no_llm_graceful(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "app.py").write_text("def add(a,b): return a+b\n", encoding="utf-8")
            result = DISCOVERY.discover(repo, ROOT / "universal" / "registry")
        self.assertIn(result["status"], {"UNKNOWN_PROVIDER", "DETECTED"})
        binding = self._binding({"provider": None, "adapter": "generic_v1", "model": None, "credential_name": None, "base_url": None})
        with tempfile.TemporaryDirectory() as tmp:
            report = REPORT.build_report({"findings": []}, self._acceptance(), Path(tmp), {"credential_present": False}, None, target_binding=binding)
        self.assertEqual(report["provider"]["verdict"], "NO_PROVIDER_DETECTED")
        self.assertTrue(report["stage2_diagnosis"]["secretless_continuation"])

    def test_workload_descriptor_is_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".costdoctor").mkdir()
            (repo / ".costdoctor" / "target-workload.json").write_text(json.dumps({"kind": "generic", "items": [{"prompt": "private", "expected": "ok"}]}), encoding="utf-8")
            descriptor = PRECHECK.workload_descriptor(repo)
        self.assertTrue(descriptor["ready"])
        self.assertEqual(descriptor["item_count"], 1)
        self.assertNotIn("private", json.dumps(descriptor))


if __name__ == "__main__":
    unittest.main()
