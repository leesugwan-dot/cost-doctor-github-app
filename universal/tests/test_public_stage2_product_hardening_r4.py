import importlib.util
import json
import shutil
import subprocess
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


REPORT = load("r4_report", ROOT / "universal/scripts/build_public_verified_savings_report.py")
PRECHECK = load("r4_precheck", ROOT / "universal/scripts/run_target_bound_precheck.py")
VALIDATOR = load("r4_validator", ROOT / "universal/scripts/independent_validate_public_stage2.py")


class ProductHardeningR4Tests(unittest.TestCase):
    def binding(self, measurement=None, static=None):
        return {
            "target_repository": "fixture-owner/repo",
            "target_ref": "main",
            "target_commit": "a" * 40,
            "target_fingerprint": "fp",
            "provider_contract": {"provider": "upstage", "model": "solar-pro3", "confidence": "STRONG", "endpoint": "https://api.upstage.ai/v1", "client_family": "openai-compatible"},
            "static_precheck": {"canonical_signal_counts": {"MODEL_CALL": 1, "RETRY_LOOP": 2, "CACHE_SIGNAL": 2}},
            "deterministic_measurement": measurement or {},
            "provider_detection": {"provider_candidates": [], "provider_groups": []},
            "workload": {"ready": False},
        }

    def static(self, findings=None, analysis=None):
        return {"findings": findings or [
            {"rule": "MODEL_CALL", "signal_count": 1, "signal_confidence": "STRONG", "source_category": "RUNTIME_CODE", "source_category_counts": {"RUNTIME_CODE": 1}},
            {"rule": "RETRY_LOOP", "signal_count": 2, "signal_confidence": "MEDIUM", "source_category": "CONFIG", "source_category_counts": {"CONFIG": 2}},
            {"rule": "CACHE_SIGNAL", "signal_count": 2, "signal_confidence": "WEAK", "source_category": "DOCS_EXAMPLE", "source_category_counts": {"DOCS_EXAMPLE": 2}},
        ], "signal_analysis": analysis or {}, "coverage": {"analyzed_files": 3, "analyzed_bytes": 600}}

    def measurement(self):
        return {"available": True, "execution": {"target_code_executed": False, "provider_calls": 0, "secret_used": False}, "context": {"candidate_chars": 800, "repeated_candidate_chars": 400, "before_token_estimate": 200, "optimized_token_estimate": 100, "avoidable_delta_tokens": 100, "repeated_token_estimate": 100, "repeated_candidate_ratio": 0.5}, "retry": {"negative_evidence": "RETRY_DISABLED_OBSERVED", "disabled_config_count": 1, "active_config_count": 0}, "cache": {"cacheable_candidate_chars": 120, "llm_relevant_occurrences": 2}, "budget": {"declared_values": [512]}}

    def test_user_markdown_hides_machine_enums_and_uses_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = REPORT.build_report(self.static(), {"local_verdict": "PASS", "workloads": []}, Path(tmp), {"credential_present": False}, None, target_binding=self.binding(self.measurement()))
            ko = REPORT.render_markdown(report, "ko")
            en = REPORT.render_markdown(report, "en")
        for text in (ko, en):
            self.assertNotIn("L2_DETERMINISTIC_MEASUREMENT", text)
            self.assertNotIn("UNKNOWN_UNTIL_MEASURED", text)
        self.assertIn("점검 우선순위", ko)
        self.assertIn("Optimization review priority", en)
        self.assertNotIn("비용 위험", ko)

    def test_disabled_retry_is_negative_evidence_and_not_high(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = REPORT.build_report(self.static(), {"local_verdict": "PASS", "workloads": []}, Path(tmp), {"credential_present": False}, None, target_binding=self.binding(self.measurement()))
        retry = next(x for x in report["stage2_diagnosis"]["findings"] if x["rule"] == "RETRY_LOOP")
        self.assertEqual(retry["verification_level"], "L1_STRUCTURAL_DIAGNOSIS")
        self.assertEqual(retry["impact_level"], "LOW")
        self.assertIn("활성 재시도 증폭", retry["improvement"])

    def test_context_before_delta_is_structural_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = REPORT.build_report(self.static(), {"local_verdict": "PASS", "workloads": []}, Path(tmp), {"credential_present": False}, None, target_binding=self.binding(self.measurement()))
            text = REPORT.render_markdown(report, "ko")
        self.assertIn("200", text)
        self.assertIn("100", text)
        self.assertIn("청구 토큰 아님", text)
        self.assertIsNone(report["user_summary"]["estimated_cost_effect"])

    def test_independent_rejects_disabled_retry_high(self):
        binding = self.binding(self.measurement())
        report = {"trust_level": "L2_DETERMINISTIC_MEASUREMENT", "verdict": "DETERMINISTIC_MEASUREMENT", "stage2_diagnosis": {"status": "COMPLETE_STAGE2", "findings": [{"rule": "RETRY_LOOP", "verification_level": "L1_STRUCTURAL_DIAGNOSIS", "impact_level": "HIGH", "deterministic_measurement": {}}]}}
        result = VALIDATOR.validate(binding, {"credential_present": False}, report)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("DISABLED_RETRY_MARKED_HIGH", result["failures"])

    def test_context_delta_invariant_is_required_for_user_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            invalid = self.measurement()
            invalid["context"].update({"before_token_estimate": 1837, "optimized_token_estimate": 0, "avoidable_delta_tokens": 3617})
            report = REPORT.build_report(self.static(), {"local_verdict": "PASS", "workloads": []}, Path(tmp), {"credential_present": False}, None, target_binding=self.binding(invalid))
            text = REPORT.render_markdown(report, "ko")
        self.assertNotIn("1,837 → 0", text)
        self.assertIn("측정 기준이 일치하지 않아", text)
        self.assertIsNone(report["user_summary"]["context_before_after"]["before_token_estimate"])

    def test_independent_rejects_invalid_l2_delta(self):
        binding = self.binding(self.measurement())
        binding["deterministic_measurement"]["context"].update({"before_token_estimate": 1837, "optimized_token_estimate": 0, "avoidable_delta_tokens": 3617})
        report = {"trust_level": "L2_DETERMINISTIC_MEASUREMENT", "verdict": "DETERMINISTIC_MEASUREMENT", "stage2_diagnosis": {"status": "COMPLETE_STAGE2", "findings": []}}
        result = VALIDATOR.validate(binding, {"credential_present": False}, report)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("L2_DETERMINISTIC_DELTA_INVARIANT_FAILED", result["failures"])

    def test_precheck_keeps_global_repetition_out_of_context_delta(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("""prompt = 'same context payload that is intentionally long enough for analysis'\nprompt = 'same context payload that is intentionally long enough for analysis'\n# ordinary repeated source line\nordinary = '""" + ("x" * 400) + "'\nordinary = '""" + ("x" * 400) + "'\n""", encoding="utf-8")
            measurement = PRECHECK._bounded_deterministic_measurement(root)
        context = measurement["context"]
        self.assertLessEqual(context["repeated_candidate_chars"], context["candidate_chars"])
        self.assertGreaterEqual(context["global_repeated_source_chars"], context["repeated_candidate_chars"])
        self.assertEqual(context["before_token_estimate"] - context["optimized_token_estimate"], context["avoidable_delta_tokens"])

    def test_node_scanner_distinguishes_categories_and_cache(self):
        node = shutil.which("node") or shutil.which("nodejs")
        self.assertIsNotNone(node, "Node.js is required for the scanner contract test")
        scanner = ROOT / "costdoctor-entry/entry/scan.mjs"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("from openai import OpenAI\nclient=OpenAI()\nclient.chat.completions.create()\nmaxRetries: 0\ncache_control='ephemeral'\n", encoding="utf-8")
            (root / "README.md").write_text("retry cache OpenAI example\n", encoding="utf-8")
            script = "import {scan} from " + json.dumps(scanner.as_uri()) + "; console.log(JSON.stringify(scan(" + json.dumps(str(root)) + ")))"
            result = subprocess.run([node, "--input-type=module", "-e", script], text=True, encoding="utf-8", errors="replace", capture_output=True, check=True)
            payload = json.loads(result.stdout)
        self.assertGreaterEqual(payload["signal_analysis"]["model_call"]["sdk_import_candidates"], 1)
        self.assertGreaterEqual(payload["signal_analysis"]["model_call"]["invocation_candidates"], 1)
        self.assertEqual(payload["signal_analysis"]["retry"]["negative_evidence"], "RETRY_DISABLED_OBSERVED")
        self.assertGreaterEqual(payload["signal_analysis"]["cache"]["llm_relevant_candidates"], 1)
        self.assertIn("source_category", payload["findings"][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
