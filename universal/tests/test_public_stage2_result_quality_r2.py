import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "universal" / "scripts" / "build_public_verified_savings_report.py"
PRECHECK_PATH = ROOT / "universal" / "scripts" / "run_target_bound_precheck.py"
DISCOVERY_PATH = ROOT / "universal" / "costdoctor" / "provider_discovery.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


REPORT = load_module("r2_report", REPORT_PATH)
PRECHECK = load_module("r2_precheck", PRECHECK_PATH)
DISCOVERY = load_module("r2_discovery", DISCOVERY_PATH)


class PublicStage2ResultQualityR2Tests(unittest.TestCase):
    def acceptance(self):
        return {"local_verdict": "PASS", "workloads": [{"quality": {"failed_phases": []}}]}

    def binding(self, *, canonical=None, raw=None, measurement=None, provider="openai", model="gpt-5.6-luna", confidence="STRONG"):
        return {
            "target_repository": "fixture-owner/fixture-repo",
            "target_ref": "main",
            "target_commit": "commit-r2",
            "target_fingerprint": "fingerprint-r2",
            "provider_contract": {"provider": provider, "adapter": "generic_v1", "model": model, "credential_name": "PROVIDER_KEY", "confidence": confidence},
            "static_precheck": {"canonical_signal_counts": canonical or {"MODEL_CALL": 3, "RETRY_LOOP": 18, "CACHE_SIGNAL": 6}, "aggregate_counts": canonical or {"MODEL_CALL": 3, "RETRY_LOOP": 18, "CACHE_SIGNAL": 6}, "raw_scan_counts": raw or {"model_call_signals": 115, "retry_signals": 11, "cache_signals": 6}},
            "deterministic_measurement": measurement or {},
            "provider_detection": {"selected": {"provider": provider, "model": model, "confidence": confidence}, "provider_candidates": [{"provider": provider, "model": model, "confidence": confidence, "score": 2}]},
            "workload": {"ready": False, "reason": "descriptor_not_required_for_stage2"},
        }

    def static(self):
        return {"findings": [{"rule": "MODEL_CALL", "signal_count": 3}, {"rule": "RETRY_LOOP", "signal_count": 18}, {"rule": "CACHE_SIGNAL", "signal_count": 6}], "savings": {"status": "UNKNOWN"}}

    def measurement(self):
        return {"schema": "costdoctor.deterministic-measurement.v1", "available": True, "measurement_grade": "L2_DETERMINISTIC_MEASUREMENT", "execution": {"target_code_executed": False, "provider_calls": 0, "secret_used": False}, "context": {"candidate_chars": 800, "repeated_candidate_chars": 400, "repeated_token_estimate": 100, "candidate_token_estimate": 200, "repeated_candidate_ratio": 0.5}, "retry": {"configured_upper_bound_attempts": 3}, "cache": {"cacheable_candidate_chars": 120}, "budget": {"declared_values": [512]}, "claim_boundary": "structural source measurement; not provider usage"}

    def test_stage2_reuses_stage1_canonical_counts_and_hides_raw_hits(self):
        binding = self.binding(raw={"model_call_signals": 115, "retry_signals": 11, "cache_signals": 99})
        with tempfile.TemporaryDirectory() as tmp:
            report = REPORT.build_report(self.static(), self.acceptance(), Path(tmp), {"credential_present": False}, None, target_binding=binding)
            markdown = REPORT.render_markdown(report)
        values = {item["rule"]: item["canonical_signal_count"] for item in report["stage2_diagnosis"]["findings"]}
        self.assertEqual(values["MODEL_CALL"], 3)
        self.assertEqual(values["RETRY_LOOP"], 18)
        self.assertNotIn("115", markdown)
        self.assertNotIn("99", markdown)
        self.assertTrue(report["stage2_diagnosis"]["raw_detector_hits_user_visible"] is False)

    def test_secretless_deterministic_measurement_promotes_to_l2(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = REPORT.build_report(self.static(), self.acceptance(), Path(tmp), {"credential_present": False}, None, target_binding=self.binding(measurement=self.measurement()))
            markdown = REPORT.render_markdown(report)
        self.assertEqual(report["trust_level"], "L2_DETERMINISTIC_MEASUREMENT")
        self.assertEqual(report["verdict"], "DETERMINISTIC_MEASUREMENT")
        self.assertIn("repeated_context_chars", json.dumps(report, ensure_ascii=False))
        self.assertNotIn("5~25%", markdown)
        self.assertIn("청구 비용 아님", markdown)

    def test_official_price_without_before_after_delta_stays_l2(self):
        preflight = {"credential_present": False, "pricing_status": "PROVIDER_PUBLISHED", "pricing_evidence": {"provider": "openai", "model": "gpt-5.6-luna", "price_grade": "PROVIDER_PUBLISHED", "source": "official", "unit_rates_usd": {"input_tokens": 1.0}}}
        with tempfile.TemporaryDirectory() as tmp:
            report = REPORT.build_report(self.static(), self.acceptance(), Path(tmp), preflight, None, target_binding=self.binding(measurement=self.measurement()))
            markdown = REPORT.render_markdown(report)
        self.assertEqual(report["trust_level"], "L2_DETERMINISTIC_MEASUREMENT")
        self.assertEqual(report["verdict"], "DETERMINISTIC_MEASUREMENT")
        self.assertIsNone(report["user_summary"]["estimated_cost_effect"])
        self.assertNotIn("가상 호출 1회", markdown)

    def test_official_price_with_reproducible_before_after_delta_promotes_to_l3(self):
        preflight = {"credential_present": False, "pricing_status": "PROVIDER_PUBLISHED", "pricing_evidence": {"provider": "openai", "model": "gpt-5.6-luna", "price_grade": "PROVIDER_PUBLISHED", "source": "official", "unit_rates_usd": {"input_tokens": 1.0}}, "pricing_binding": {"strict_equality": True}}
        measurement = self.measurement()
        measurement["context"].update({"before_token_estimate": 200, "optimized_token_estimate": 100, "avoidable_delta_tokens": 100})
        with tempfile.TemporaryDirectory() as tmp:
            report = REPORT.build_report(self.static(), self.acceptance(), Path(tmp), preflight, None, target_binding=self.binding(measurement=measurement))
            markdown = REPORT.render_markdown(report)
        self.assertEqual(report["trust_level"], "L3_ESTIMATED_COST_SAVINGS")
        self.assertEqual(report["verdict"], "ESTIMATED_SAVINGS")
        self.assertIsNotNone(report["user_summary"]["estimated_cost_effect"])
        self.assertIn("가상 호출 1회", markdown)
        self.assertNotIn("월간 환산:", markdown)

    def test_price_without_token_binding_stays_l2(self):
        preflight = {"credential_present": False, "pricing_status": "PROVIDER_PUBLISHED", "pricing_evidence": {"provider": "openai", "model": "gpt-5.6-luna", "price_grade": "PROVIDER_PUBLISHED", "unit_rates_usd": {"input_tokens": 1.0}}}
        measurement = self.measurement()
        measurement["context"]["repeated_token_estimate"] = 0
        with tempfile.TemporaryDirectory() as tmp:
            report = REPORT.build_report(self.static(), self.acceptance(), Path(tmp), preflight, None, target_binding=self.binding(measurement=measurement))
        self.assertEqual(report["trust_level"], "L2_DETERMINISTIC_MEASUREMENT")
        self.assertIsNone(report["user_summary"]["estimated_cost_effect"])

    def test_two_generic_fixtures_share_core_without_target_specific_claim(self):
        measurements = [self.measurement(), {"available": True, "measurement_grade": "L2_DETERMINISTIC_MEASUREMENT", "execution": {"target_code_executed": False, "provider_calls": 0, "secret_used": False}, "context": {"candidate_chars": 0, "repeated_candidate_chars": 0, "repeated_token_estimate": 0}, "retry": {"configured_upper_bound_attempts": 2}, "cache": {}, "budget": {"declared_values": []}}]
        providers = [("openai", "gpt-5.6-luna"), ("ollama", "local-fixture-v1")]
        for measurement, (provider, model) in zip(measurements, providers):
            with tempfile.TemporaryDirectory() as tmp:
                report = REPORT.build_report(self.static(), self.acceptance(), Path(tmp), {"credential_present": False}, None, target_binding=self.binding(measurement=measurement, provider=provider, model=model, confidence="MEDIUM"))
            self.assertNotIn("active-project-reliability-demo", json.dumps(report))
            self.assertIn(report["trust_level"], {"L1_STRUCTURAL_DIAGNOSIS", "L2_DETERMINISTIC_MEASUREMENT"})

    def test_offline_measurement_never_executes_or_calls_provider(self):
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            left_path, right_path = Path(left), Path(right)
            (left_path / "app.py").write_text("retry=2\ncache_control='x'\ncontext='same payload'\ncontext='same payload'\nmax_tokens=512\n", encoding="utf-8")
            (right_path / "README.md").write_text("plain repository without model calls\n", encoding="utf-8")
            first = PRECHECK._bounded_deterministic_measurement(left_path)
            second = PRECHECK._bounded_deterministic_measurement(right_path)
        self.assertEqual(first["execution"], {"target_code_executed": False, "provider_calls": 0, "secret_used": False})
        self.assertEqual(second["execution"]["provider_calls"], 0)
        self.assertTrue(first["available"])
        self.assertFalse(second["available"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
