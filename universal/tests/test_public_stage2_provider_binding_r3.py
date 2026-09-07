import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


DISCOVERY = load("r3_discovery", ROOT / "universal" / "costdoctor" / "provider_discovery.py")
REPORT = load("r3_report", ROOT / "universal" / "scripts" / "build_public_verified_savings_report.py")
INDEPENDENT = load("r3_independent", ROOT / "universal" / "scripts" / "independent_validate_public_stage2.py")


class ProviderBindingR3Tests(unittest.TestCase):
    REGISTRY = ROOT / "universal" / "registry"

    def discover(self, source):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            (repo / "app.py").write_text(source, encoding="utf-8")
            return DISCOVERY.discover(repo, self.REGISTRY)

    def test_upstage_endpoint_wins_over_openai_compatible_sdk(self):
        result = self.discover("from langchain_openai import ChatOpenAI\nclient = ChatOpenAI(base_url='https://api.upstage.ai/v1', api_key=UPSTAGE_API_KEY, model='solar-pro3')\n")
        selected = result["selected"]
        self.assertEqual(result["status"], "DETECTED")
        self.assertEqual(selected["provider"], "upstage")
        self.assertEqual(selected["model"], "solar-pro3")
        self.assertEqual(selected["client_family"], "openai-compatible")
        self.assertEqual(selected["identity_source"], "explicit_endpoint")

    def test_direct_openai_is_explicitly_bound(self):
        result = self.discover("from openai import OpenAI\nclient = OpenAI(base_url='https://api.openai.com/v1')\nmodel='gpt-5.6-luna'\n")
        self.assertEqual(result["selected"]["provider"], "openai")
        self.assertEqual(result["selected"]["model"], "gpt-5.6-luna")

    def test_custom_compatible_endpoint_is_not_openai(self):
        result = self.discover("from openai import OpenAI\nclient = OpenAI(base_url='https://custom.example.com/v1')\nmodel='unknown-model'\n")
        self.assertEqual(result["selected"]["provider"], "OPENAI_COMPATIBLE_CUSTOM")
        self.assertIsNone(result["selected"]["model"])

    def test_ollama_has_no_inferred_model(self):
        result = self.discover("import ollama\nollama.generate(model='local-model')\n")
        self.assertEqual(result["selected"]["provider"], "ollama")
        self.assertIsNone(result["selected"]["model"])

    def test_multi_provider_is_grouped(self):
        result = self.discover("from openai import OpenAI\nOpenAI(base_url='https://api.openai.com/v1')\nfrom anthropic import Anthropic\nAnthropic(base_url='https://api.anthropic.com')\n")
        self.assertEqual(result["status"], "MULTIPLE_PROVIDERS")
        self.assertEqual(result["selected"]["provider"], "MULTIPLE_PROVIDERS")
        self.assertGreaterEqual(len(result["provider_groups"]), 2)

    def test_no_llm_is_unknown(self):
        result = self.discover("def add(a, b):\n    return a + b\n")
        self.assertIsNone(result["selected"]["provider"])
        self.assertEqual(result["status"], "UNKNOWN_PROVIDER")

    def measurement(self):
        return {"available": True, "execution": {"target_code_executed": False, "provider_calls": 0, "secret_used": False}, "context": {"candidate_token_estimate": 200, "repeated_token_estimate": 40, "before_token_estimate": 200, "optimized_token_estimate": 160, "avoidable_delta_tokens": 40}, "retry": {"configured_upper_bound_attempts": 3}, "cache": {"cacheable_candidate_chars": 120}, "budget": {"declared_values": []}}

    def binding(self, contract):
        return {"target_repository": "owner/fixture", "target_commit": "commit-r3", "target_fingerprint": "fingerprint-r3", "provider_contract": contract, "deterministic_measurement": self.measurement(), "provider_resolution": {"status": contract.get("provider_identity_status", "DETECTED")}}

    def test_independent_rejects_upstage_endpoint_with_openai_price(self):
        contract = {"provider": "openai", "model": "gpt-5.6-luna", "endpoint": "https://api.upstage.ai/v1", "base_url": "https://api.upstage.ai/v1", "client_family": "openai-compatible", "confidence": "STRONG", "provider_identity_status": "DETECTED", "conflicts": []}
        binding = self.binding(contract)
        preflight = {"pricing_status": "PROVIDER_PUBLISHED", "pricing_evidence": {"provider": "openai", "model": "gpt-5.6-luna"}, "pricing_binding": {"strict_equality": True}}
        with tempfile.TemporaryDirectory() as tmp:
            report = REPORT.build_report({"findings": [{"rule": "MODEL_CALL", "signal_count": 1}]}, {"local_verdict": "PASS", "workloads": []}, Path(tmp), preflight, None, target_binding=binding)
        independent = INDEPENDENT.validate(binding, preflight, report)
        self.assertIn("UPSTAGE_ENDPOINT_OPENAI_PRICING_FALSE_PASS", independent["failures"])
        self.assertEqual(independent["verdict"], "FAIL")

    def test_retry_without_observed_measurement_is_l1(self):
        contract = {"provider": "upstage", "model": "solar-pro3", "endpoint": "https://api.upstage.ai/v1", "client_family": "openai-compatible", "confidence": "STRONG", "provider_identity_status": "DETECTED", "conflicts": []}
        with tempfile.TemporaryDirectory() as tmp:
            report = REPORT.build_report({"findings": [{"rule": "RETRY_LOOP", "signal_count": 3}, {"rule": "MODEL_CALL", "signal_count": 1}]}, {"local_verdict": "PASS", "workloads": []}, Path(tmp), {"credential_present": False}, None, target_binding=self.binding(contract))
        levels = {item["rule"]: item["verification_level"] for item in report["stage2_diagnosis"]["findings"]}
        self.assertEqual(levels["RETRY_LOOP"], "L1_STRUCTURAL_DIAGNOSIS")
        self.assertEqual(levels["MODEL_CALL"], "L2_DETERMINISTIC_MEASUREMENT")

    def test_multi_provider_cannot_reach_l3(self):
        contract = {"provider": "MULTIPLE_PROVIDERS", "model": None, "client_family": "multiple", "confidence": "NONE", "provider_identity_status": "MULTIPLE_PROVIDERS", "conflicts": ["MULTIPLE_EXPLICIT_PROVIDERS"]}
        preflight = {"credential_present": False, "pricing_status": "PROVIDER_PUBLISHED", "pricing_evidence": {"provider": "openai", "model": "gpt-5.6-luna"}, "pricing_binding": {"strict_equality": False}}
        with tempfile.TemporaryDirectory() as tmp:
            report = REPORT.build_report({"findings": [{"rule": "MODEL_CALL", "signal_count": 1}]}, {"local_verdict": "PASS", "workloads": []}, Path(tmp), preflight, None, target_binding=self.binding(contract))
        self.assertNotEqual(report["trust_level"], "L3_ESTIMATED_COST_SAVINGS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
