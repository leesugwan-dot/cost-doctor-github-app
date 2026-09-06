from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "universal"))

from costdoctor.benchmark import build_benchmark_packet, compare_bindings  # noqa: E402
from costdoctor.canonical import sha256_json, utc_now  # noqa: E402
from costdoctor.quality import evaluate_quality  # noqa: E402
from costdoctor.registry import PricingRegistry  # noqa: E402
from costdoctor.pricing import PricingEngine  # noqa: E402
from costdoctor.report import render_report  # noqa: E402
from costdoctor.validator import validate_packet  # noqa: E402


class BenchmarkValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pricing = PricingEngine(PricingRegistry(ROOT / "universal" / "registry" / "pricing"))

    def binding(self):
        return {
            "goal": "same",
            "input_fingerprint": "1" * 64,
            "quality_criteria": "exact",
            "latency_limit_ms": 100,
            "tool_permissions": [],
            "repetitions": 2,
            "environment_fingerprint": "env",
            "workload_fingerprint": "2" * 64,
            "commit": "a" * 40,
        }

    def event(self, event_id, run_id, tokens, model="fixture-mid-v1", quality=1.0):
        event = {
            "schema": "costdoctor.usage-event.v1",
            "event_id": event_id,
            "workload_id": "w",
            "run_id": run_id,
            "sequence": 0,
            "provider": "generic",
            "model": model,
            "started_at": utc_now(),
            "ended_at": utc_now(),
            "success": quality == 1.0,
            "error_class": None,
            "usage": {"input_tokens": tokens, "output_tokens": 10, "cached_input_tokens": 0, "cache_write_tokens": 0, "reasoning_tokens": 0, "tool_calls": 0, "call_count": 1, "retry_count": 0},
            "billed_units": {},
            "provider_reported": False,
            "measurement_source": "LOCAL_DETERMINISTIC_ACTUAL_RUN",
            "latency_ms": 1,
            "cache_hit": False,
            "tool_sequence": [],
            "source_binding": {"commit": "a" * 40},
            "environment_fingerprint": "env",
            "workload_fingerprint": "2" * 64,
            "input_fingerprint": "3" * 64,
            "context_fingerprint": "4" * 64,
            "quality_score": quality,
            "metadata": {},
            "batch": False,
        }
        event["event_digest"] = sha256_json(event)
        return event

    def packet(self, after_tokens=100, after_quality=1.0, model="fixture-mid-v1"):
        before = [self.event("b1", "br1", 1000), self.event("b2", "br2", 1000)]
        after = [self.event("a1", "ar1", after_tokens, model, after_quality), self.event("a2", "ar2", after_tokens, model, after_quality)]
        prices_before = [self.pricing.price_event(event) for event in before]
        prices_after = [self.pricing.price_event(event) for event in after]
        binding = self.binding()
        rollback = {
            "actual_status": "PASS",
            "baseline_metrics_fingerprint": "x",
            "restored_before_metrics_fingerprint": "x",
            "after_metrics_fingerprint": "y",
            "reapplied_after_metrics_fingerprint": "y",
        }
        return build_benchmark_packet("w", before, after, prices_before, prices_after, binding, deepcopy(binding), 1.0, rollback, [], {"verdict": "NOT_APPLICABLE"}, "TEST_FIXTURE")

    def refresh_digest(self, packet):
        payload = deepcopy(packet)
        payload.pop("producer_digest", None)
        packet["producer_digest"] = sha256_json(payload)

    def test_binding_match(self):
        self.assertEqual(compare_bindings(self.binding(), self.binding())["verdict"], "PASS")

    def test_binding_mismatch_blocks(self):
        other = self.binding()
        other["goal"] = "different"
        self.assertEqual(compare_bindings(self.binding(), other)["verdict"], "BLOCKED")

    def test_quality_pass(self):
        self.assertEqual(evaluate_quality([1, 1], [1, 1], 1)["verdict"], "PASS")

    def test_quality_regression_fails(self):
        self.assertEqual(evaluate_quality([1, 1], [0.8, 0.8], 0.5)["reason"], "QUALITY_REGRESSION")

    def test_quality_missing_needs_evidence(self):
        self.assertEqual(evaluate_quality([], [1], 1)["verdict"], "NEEDS_EVIDENCE")

    def test_independent_validator_passes_good_packet(self):
        result = validate_packet(self.packet())
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["claim_level"], 5)

    def test_tampered_event_is_rejected(self):
        packet = self.packet()
        packet["after"]["events"][0]["usage"]["input_tokens"] += 1
        self.refresh_digest(packet)
        self.assertIn("AFTER_EVENT_DIGEST_MISMATCH", validate_packet(packet)["failures"])

    def test_wrong_commit_binding_is_rejected(self):
        packet = self.packet()
        packet["after"]["events"][0]["source_binding"]["commit"] = "b" * 40
        event = packet["after"]["events"][0]
        digestable = deepcopy(event)
        digestable.pop("event_digest")
        event["event_digest"] = sha256_json(digestable)
        self.refresh_digest(packet)
        self.assertIn("AFTER_COMMIT_BINDING_MISMATCH", validate_packet(packet)["failures"])

    def test_wrong_workload_binding_is_rejected(self):
        packet = self.packet()
        packet["after"]["events"][0]["workload_fingerprint"] = "9" * 64
        event = packet["after"]["events"][0]
        digestable = deepcopy(event)
        digestable.pop("event_digest")
        event["event_digest"] = sha256_json(digestable)
        self.refresh_digest(packet)
        self.assertIn("AFTER_WORKLOAD_BINDING_MISMATCH", validate_packet(packet)["failures"])

    def test_tampered_price_snapshot_is_rejected(self):
        packet = self.packet()
        packet["after"]["prices"][0]["pricing_snapshot"]["unit_rates_usd"]["input_tokens"] = 99
        self.refresh_digest(packet)
        failures = validate_packet(packet)["failures"]
        self.assertIn("AFTER_PRICE_RECOMPUTE_MISMATCH", failures)

    def test_unknown_price_blocks_verified_savings(self):
        packet = self.packet(model="future-model-x")
        result = validate_packet(packet)
        self.assertEqual(packet["claim"]["status"], "UNKNOWN")
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIsNone(result["verified_savings_usd"])

    def test_quality_loss_is_not_claimed_as_savings(self):
        packet = self.packet(after_quality=0.0)
        self.assertEqual(packet["claim"]["status"], "FAIL")
        self.assertIsNone(packet["claim"]["verified_savings_usd"])

    def test_reports_have_korean_and_english_paths(self):
        packet = self.packet()
        validation = validate_packet(packet)
        self.assertIn("검증 절감액", render_report(packet, validation, "ko"))
        self.assertIn("Verified savings", render_report(packet, validation, "en"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
