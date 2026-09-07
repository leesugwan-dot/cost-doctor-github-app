import json
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("stage2_report", ROOT / "universal" / "scripts" / "build_public_verified_savings_report.py")
REPORT = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(REPORT)


class UniversalStage2GeneralizationTests(unittest.TestCase):
    def test_workflow_has_no_fixture_default_or_provider_secret_literal(self):
        text = (ROOT / ".github" / "workflows" / "public-verified-savings.yml").read_text(encoding="utf-8")
        self.assertNotIn("active-project-reliability-demo", text)
        self.assertNotIn("UPSTAGE_API_KEY", text)
        self.assertIn("provider_secret_name", text)
        self.assertIn("run_universal_provider_preflight.py", text)
        self.assertIn("run_provider_abc.py", text)

    def test_provider_registry_exposes_requested_families_as_data(self):
        rows = []
        for path in (ROOT / "universal" / "registry" / "providers").glob("*.json"):
            rows.extend(json.loads(path.read_text(encoding="utf-8")).get("rows", []))
        providers = {row.get("provider") for row in rows}
        for provider in {"openai", "anthropic", "gemini", "azure_openai", "bedrock", "upstage", "openai_compatible", "ollama", "unknown_custom"}:
            self.assertIn(provider, providers)

    def test_no_llm_fixture_is_not_blocked_by_provider_secret(self):
        report_script = ROOT / "universal" / "scripts" / "build_public_verified_savings_report.py"
        text = report_script.read_text(encoding="utf-8")
        self.assertIn("SECRET_OPTIONAL_FOR_STAGE2", text)
        self.assertIn("NO_PROVIDER_DETECTED", text)
        self.assertIn("STRUCTURAL_DIAGNOSIS", text)
        self.assertNotIn("target-existing-synthetic-solar-tool-call", text)

    def test_unknown_price_is_not_promoted(self):
        preflight = (ROOT / "universal" / "scripts" / "run_universal_provider_preflight.py").read_text(encoding="utf-8")
        self.assertIn("UNKNOWN_PRICE_BLOCKED", preflight)
        self.assertIn("stage2_continuation", preflight)

    def test_same_stage2_schema_across_provider_and_no_llm_fixtures(self):
        contracts = [
            {"provider": "openai", "adapter": "openai_v1", "model": "gpt-test", "credential_name": "OPENAI_API_KEY", "base_url": "https://api.openai.com/v1"},
            {"provider": "upstage", "adapter": "upstage_openai_compatible_chat_v1", "model": "solar-pro3", "credential_name": "UPSTAGE_API_KEY", "base_url": "https://api.upstage.ai/v1"},
            {"provider": "ollama", "adapter": "ollama_v1", "model": "local-fixture-v1", "credential_name": None, "base_url": "http://localhost:11434/api"},
            {"provider": None, "adapter": "generic_v1", "model": None, "credential_name": None, "base_url": None},
        ]
        for contract in contracts:
            binding = {"target_repository": "owner/repository", "target_ref": "main", "target_commit": "abc123", "target_fingerprint": "fp-" + str(contract["provider"]), "provider_contract": contract, "static_precheck": {"aggregate_counts": {"files": 2, "retry_signals": 1, "cache_signals": 0, "model_call_signals": 1}}, "workload": {"ready": False}}
            with tempfile.TemporaryDirectory() as tmp:
                report = REPORT.build_report({"findings": []}, {"local_verdict": "PASS", "workloads": []}, Path(tmp), {"credential_present": False}, None, target_binding=binding)
            self.assertEqual(report["schema"], "costdoctor.public-verified-savings.universal-stage2.v3")
            self.assertTrue(report["stage2_diagnosis"]["secretless_continuation"])
            self.assertIn(report["verdict"], {"STRUCTURAL_DIAGNOSIS", "ESTIMATED_SAVINGS"})


if __name__ == "__main__":
    unittest.main()
