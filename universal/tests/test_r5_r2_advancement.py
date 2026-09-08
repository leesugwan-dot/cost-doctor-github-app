import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PRECHECK = load_module("r5_precheck", "universal/scripts/run_target_bound_precheck.py")
REPORT = load_module("r5_report", "universal/scripts/build_public_verified_savings_report.py")


class R5R2AdvancementTests(unittest.TestCase):
    def test_runtime_path_and_non_runtime_calls_are_separate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "runtime.py").write_text(
                "from openai import OpenAI\nclient = OpenAI()\n"
                "payload = {'prompt': 'same context'}\n"
                "client.chat.completions.create(messages=payload, max_retries=0)\n",
                encoding="utf-8",
            )
            (root / "tests").mkdir()
            (root / "tests" / "sample_test.py").write_text("client.chat.completions.create(messages={'prompt': 'fixture'})\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "example.md").write_text("client.chat.completions.create(messages={'prompt': 'docs'})\n", encoding="utf-8")
            (root / ".env").write_text("client.chat.completions.create(secret='do-not-read')\n", encoding="utf-8")
            measurement = PRECHECK._bounded_deterministic_measurement(root)
            runtime = measurement["runtime"]
            self.assertEqual(runtime["runtime_invocation_count"], 1)
            self.assertEqual(runtime["test_eval_invocation_count"], 1)
            self.assertEqual(runtime["docs_example_invocation_count"], 1)
            self.assertGreaterEqual(measurement["retry"]["disabled_config_count"], 1)
            self.assertEqual(measurement["retry"]["negative_evidence"], "RETRY_DISABLED_OBSERVED")
            self.assertTrue(all(row["relative_path"] != ".env" for row in measurement["request_paths"]))
            self.assertTrue(all("C:\\" not in row["relative_path"] for row in measurement["request_paths"]))

    def test_read_before_limit_and_cache_families_are_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "large.py").write_bytes(b"x" * (PRECHECK.MAX_MEASUREMENT_FILE_BYTES + 1))
            (root / "cache.py").write_text(
                "prompt = 'stable'\ncache_control = {'type': 'ephemeral'}\n"
                "file cache = True\n",
                encoding="utf-8",
            )
            measurement = PRECHECK._bounded_deterministic_measurement(root)
            self.assertGreaterEqual(measurement["scope"]["skipped_due_to_size"], 1)
            self.assertGreaterEqual(measurement["cache"]["llm_relevant_occurrences"], 1)
            self.assertGreaterEqual(measurement["cache"]["ordinary_cache_occurrences"], 1)
            self.assertEqual(measurement["cache"]["hit_rate"], "UNKNOWN")
            self.assertEqual(measurement["cache"]["prefix_stability"], "UNVERIFIED")

    def test_report_downgrades_non_runtime_model_signal_and_exposes_safe_location(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "tests").mkdir()
            (root / "tests" / "fixture.py").write_text("client.chat.completions.create(messages={'prompt': 'fixture'})\n", encoding="utf-8")
            measurement = PRECHECK._bounded_deterministic_measurement(root)
            binding = {
                "target_repository": "owner/repo",
                "target_ref": "main",
                "target_commit": "a" * 40,
                "target_fingerprint": "b" * 64,
                "provider_contract": {"provider": "openai", "model": "gpt-test", "confidence": "WEAK", "provider_identity_status": "DETECTED"},
                "static_precheck": {"canonical_signal_counts": {"MODEL_CALL": 1}},
                "deterministic_measurement": measurement,
                "provider_detection": {"status": "DETECTED", "provider_candidates": []},
                "workload": {"ready": False},
            }
            static = {"findings": [{"rule": "MODEL_CALL", "signal_count": 1, "source_category": "TEST_EVAL", "signal_confidence": "WEAK"}], "coverage": {"analyzed_files": 1, "analyzed_bytes": 80}}
            report = REPORT.build_report(static, {"local_verdict": "PASS", "workloads": []}, root, {"credential_present": False}, None, target_binding=binding)
            finding = next(item for item in report["stage2_diagnosis"]["findings"] if item["rule"] == "MODEL_CALL")
            self.assertEqual(finding["impact_level"], "LOW")
            self.assertEqual(finding["runtime_impact"]["runtime_invocation_count"], 0)
            text = REPORT.render_markdown(report, "en")
            self.assertIn("no production runtime call confirmed", text)
            self.assertIn("Evidence status", text)
            self.assertIn("tests/fixture.py", text)


if __name__ == "__main__":
    unittest.main()
