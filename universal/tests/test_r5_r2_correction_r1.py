from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "universal"))

from costdoctor.cache_economics import break_even_hit_rate  # noqa: E402
from costdoctor.coding_agents import CodingAgentRegistry, collect_coding_agent_usage  # noqa: E402
from costdoctor.retry_semantics import normalize_retry_layers  # noqa: E402


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


REPORT = load_module("r5_correction_report", ROOT / "universal" / "scripts" / "build_public_verified_savings_report.py")
VALIDATOR = load_module("r5_correction_validator", ROOT / "universal" / "scripts" / "independent_validate_public_stage2.py")
PRECHECK = load_module("r5_correction_precheck_test", ROOT / "universal" / "scripts" / "run_target_bound_precheck.py")


class R5R2CorrectionTests(unittest.TestCase):
    def binding(self, measurement):
        return {
            "target_repository": "fixture-owner/fixture",
            "target_ref": "main",
            "target_commit": "target-commit",
            "tool_commit": "tool-commit",
            "target_fingerprint": "f" * 64,
            "provider_contract": {"provider": "upstage", "model": "solar-pro3", "confidence": "STRONG", "provider_identity_status": "DETECTED", "endpoint": "https://api.upstage.ai/v1"},
            "provider_detection": {"selected": {"provider": "upstage", "model": "solar-pro3"}},
            "static_precheck": {"canonical_signal_counts": {"MODEL_CALL": 3, "RETRY_LOOP": 20, "CACHE_SIGNAL": 6}},
            "deterministic_measurement": measurement,
            "workload": {"ready": False},
        }

    def static(self):
        return {"findings": [{"rule": "MODEL_CALL", "signal_count": 3}, {"rule": "RETRY_LOOP", "signal_count": 20}, {"rule": "CACHE_SIGNAL", "signal_count": 6}]}

    def measurement(self):
        return {
            "available": True,
            "execution": {"target_code_executed": False, "provider_calls": 0, "secret_used": False},
            "context": {"candidate_chars": 400, "repeated_candidate_chars": 100, "before_token_estimate": 100, "optimized_token_estimate": 75, "avoidable_delta_tokens": 25, "repeated_token_estimate": 25, "delta_invariant": {"status": "PASS"}},
            "runtime": {"runtime_invocation_count": 1, "test_eval_invocation_count": 2, "docs_example_invocation_count": 1, "call_path_evidence": [{"call_kind": "runtime_invocation", "relative_path": "src/app.py", "line_start": 10, "line_end": 10, "source_category": "RUNTIME_CODE"}, {"call_kind": "test_eval_invocation", "relative_path": "tests/app.py", "line_start": 20, "line_end": 20, "source_category": "TEST_EVAL"}, {"call_kind": "docs_example_invocation", "relative_path": "README.md", "line_start": 30, "line_end": 30, "source_category": "DOCS_EXAMPLE"}]},
            "request_paths": [{"call_kind": "runtime_invocation", "relative_path": "src/app.py", "line_start": 10, "line_end": 10, "source_category": "RUNTIME_CODE"}, {"call_kind": "test_eval_invocation", "relative_path": "tests/app.py", "line_start": 20, "line_end": 20, "source_category": "TEST_EVAL"}, {"call_kind": "docs_example_invocation", "relative_path": "README.md", "line_start": 30, "line_end": 30, "source_category": "DOCS_EXAMPLE"}],
            "cache": {"cacheable_candidate_chars": 100, "llm_relevant_occurrences": 1, "ordinary_cache_occurrences": 2, "hit_rate": "UNKNOWN", "prefix_stability": "UNVERIFIED", "billing_effect": "UNKNOWN", "llm_cache_evidence": []},
            "retry": {"disabled_config_count": 1, "active_config_count": 0, "negative_evidence": "RETRY_DISABLED_OBSERVED", "evidence": []},
            "budget": {"declared_values": []},
        }

    def report(self, measurement=None):
        return REPORT.build_report(self.static(), {"local_verdict": "PASS", "workloads": []}, Path(tempfile.mkdtemp()), {"credential_present": False, "pricing_status": "PROVIDER_PUBLISHED", "pricing_evidence": {"provider": "upstage", "model": "solar-pro3", "unit_rates_usd": {"input_tokens": 1.0}}}, None, target_binding=self.binding(measurement or self.measurement()))

    def test_unbound_repository_repetition_cannot_be_l3(self):
        report = self.report()
        self.assertEqual(report["trust_level"], "L2_DETERMINISTIC_MEASUREMENT")
        self.assertIsNone(report["user_summary"]["estimated_cost_effect"])
        self.assertNotEqual(report["verdict"], "ESTIMATED_SAVINGS")

    def test_priority_not_high_from_call_existence_or_unknown_cache(self):
        report = self.report()
        self.assertNotEqual(report["user_summary"]["optimization_priority"], "높음")
        self.assertFalse(any(row.get("runtime_cost_impact") for row in report["stage2_diagnosis"]["findings"]))
        self.assertEqual(report["user_summary"]["priority_reason"], "RUNTIME_CANDIDATE_WASTE_UNPROVEN")

    def test_runtime_locations_are_separate_and_actionable(self):
        report = self.report()
        model = next(row for row in report["stage2_diagnosis"]["findings"] if row["rule"] == "MODEL_CALL")
        self.assertEqual([row["relative_path"] for row in model["locations"]], ["src/app.py"])
        self.assertEqual(model["location_groups"]["test_eval"][0]["relative_path"], "tests/app.py")
        self.assertTrue(model["action_plan"]["ko"] and model["action_plan"]["en"])
        self.assertTrue(model["finding_id"].startswith("finding-"))
        markdown = REPORT.render_markdown(report, "ko")
        runtime_line = next(line for line in markdown.splitlines() if "runtime 호출 후보" in line)
        self.assertNotIn("tests/app.py", runtime_line)
        self.assertIn("테스트/평가 근거", markdown)

    def test_ko_en_semantics_match(self):
        report = self.report()
        self.assertEqual(VALIDATOR._semantic_projection(report), VALIDATOR._semantic_projection(report))
        self.assertEqual(REPORT.HUMAN_LEVELS[report["trust_level"]], "무료 정량 측정")
        self.assertEqual(REPORT.HUMAN_LEVELS_EN[report["trust_level"]], "Free deterministic measurement")

    def test_cache_break_even_and_retry_layers(self):
        self.assertEqual(break_even_hit_rate(input_tokens=None, uncached_rate_usd=None, cached_rate_usd=None)["status"], "UNKNOWN")
        self.assertEqual(break_even_hit_rate(input_tokens=1000, uncached_rate_usd="0.01", cached_rate_usd="0.002", write_cost_usd="0.000001")["status"], "AVAILABLE")
        self.assertEqual(normalize_retry_layers([{"kind": "stop_after_attempt", "value": 3}, {"kind": "max_retries", "value": 2}])["total_attempts_upper_bound"], 9)
        self.assertEqual(normalize_retry_layers([{"kind": "dynamic", "value": None}])["status"], "UNKNOWN")

    def test_python_typescript_dynamic_matrix_is_secretless(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("if enabled:\n  client.invoke(payload)\n", encoding="utf-8")
            (root / "src" / "app.ts").write_text("client.responses.create({model: 'fixture'})\n", encoding="utf-8")
            measured = PRECHECK._bounded_deterministic_measurement(root)
        self.assertEqual(measured["execution"]["provider_calls"], 0)
        self.assertEqual(measured["execution"]["target_code_executed"], False)
        self.assertGreaterEqual(measured["runtime"]["runtime_invocation_count"], 2)

    def test_coding_importer_profiles_and_unknown_usage(self):
        registry = CodingAgentRegistry(ROOT / "universal" / "registry" / "agents")
        for agent, source in (("codex", "CODEX_AVAILABLE_USAGE"), ("claude-code", "CLAUDE_CODE_AVAILABLE_USAGE")):
            result = collect_coding_agent_usage(registry.resolve(agent), {"usage": {"input_tokens": 2, "output_tokens": 1}})
            self.assertEqual(result["measurement_source"], source)
            self.assertFalse(result["measurement"]["actual_provider_usage"])
        unknown = collect_coding_agent_usage(registry.resolve("codex"), {})
        self.assertEqual(unknown["measurement"]["grade"], "UNKNOWN")

    def test_finding_id_is_stable_for_same_input(self):
        left = self.report()
        right = self.report()
        self.assertEqual([x["finding_id"] for x in left["stage2_diagnosis"]["findings"]], [x["finding_id"] for x in right["stage2_diagnosis"]["findings"]])

    def test_independent_false_pass_guards_reject_tampering(self):
        report = self.report()
        report["trust_level"] = "L3_ESTIMATED_COST_SAVINGS"
        report["verdict"] = "ESTIMATED_SAVINGS"
        preflight = {"pricing_status": "PROVIDER_PUBLISHED", "pricing_evidence": {"provider": "upstage", "model": "solar-pro3"}, "pricing_binding": {"strict_equality": True}}
        result = VALIDATOR.validate(self.binding(self.measurement()), preflight, report)
        self.assertIn("L3_REQUEST_PAYLOAD_BINDING_REQUIRED", result["failures"])
        report = self.report()
        report["user_summary"]["optimization_priority"] = "높음"
        result = VALIDATOR.validate(self.binding(self.measurement()), preflight, report)
        self.assertIn("HIGH_WITHOUT_RUNTIME_COST_IMPACT", result["failures"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
