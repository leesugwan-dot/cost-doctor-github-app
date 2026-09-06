from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "universal"))

from costdoctor.evidence import UsageImporter  # noqa: E402
from costdoctor.pricing import PricingEngine  # noqa: E402
from costdoctor.registry import ModelRegistry, PricingRegistry, ProviderRegistry  # noqa: E402
from costdoctor.three_stage import build_three_stage_packet, render_three_stage_summary_ko  # noqa: E402
from costdoctor.three_stage_validator import run_false_pass_probes, validate_three_stage  # noqa: E402


class ThreeStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = ModelRegistry(ROOT / "universal" / "registry" / "models")
        cls.providers = ProviderRegistry(ROOT / "universal" / "registry" / "providers")
        cls.pricing = PricingEngine(PricingRegistry(ROOT / "universal" / "registry" / "pricing"))
        cls.importer = UsageImporter(cls.models, cls.providers)
        cls.binding = {"goal": "same", "input_fingerprint": "a" * 64, "quality_criteria": ["exact"], "latency_limit_ms": 100, "tool_permissions": [], "repetitions": 1, "environment_fingerprint": "env", "workload_fingerprint": "b" * 64, "commit": "c" * 40}

    def phase(self, name: str, tokens: int, overhead: str):
        records = [{"event_id": f"{name}-{sequence}", "sequence": sequence, "started_at": "2026-09-06T00:00:00+00:00", "ended_at": "2026-09-06T00:00:01+00:00", "success": True, "usage": {"input_tokens": tokens, "output_tokens": 10}, "latency_ms": 1, "quality_score": 1.0, "measurement_source": "BYTE_PROXY", "input_fingerprint": f"item-{sequence}"} for sequence in range(2)]
        evidence = self.importer.normalize_records(records, {"workload_id": "three", "run_id": name, "provider": "generic", "model": "fixture-mid-v1", "source_binding": {"commit": "c" * 40}, "environment_fingerprint": "env", "workload_fingerprint": "b" * 64})
        return {"events": evidence["events"], "prices": [self.pricing.price_event(event) for event in evidence["events"]], "binding": dict(self.binding), "overhead": {"cost_usd": overhead, "included": True}}

    def packet(self):
        return build_three_stage_packet("three", {"raw": self.phase("raw", 1000, "0.000000000"), "engine": self.phase("engine", 400, "0.000010000"), "engine_costdoctor": self.phase("engine_costdoctor", 100, "0.000020000")}, quality_threshold=1.0, rollback={"actual_status": "PASS", "baseline_metrics_fingerprint": "a", "restored_before_metrics_fingerprint": "a", "after_metrics_fingerprint": "b", "reapplied_after_metrics_fingerprint": "b"}, context_receipts={"raw": {"measurement_grade": "BYTE_CONTEXT_ONLY"}, "engine": {"retention_check": "PASS"}, "engine_costdoctor": {"retention_check": "PASS"}}, claim_scope="deterministic public fixture; not production savings")

    def test_three_stage_recomputed_and_truthfully_graded(self):
        packet = self.packet()
        self.assertEqual(packet["claim"]["status"], "MEASURED_PENDING_INDEPENDENT_VALIDATION")
        self.assertEqual(packet["claim"]["grade"], "NON_PROVIDER_OR_UNVERIFIED_PRICE_MEASUREMENT")
        result = validate_three_stage(packet)
        self.assertEqual(result["verdict"], "PASS")
        self.assertFalse(result["provider_actual_claim"])
        self.assertIsNone(result["verified_savings_usd"])
        self.assertIsNotNone(result["independently_recomputed_savings_usd"])
        self.assertIn("원래 방식", render_three_stage_summary_ko(packet, result))

    def test_false_pass_probes_all_block(self):
        result = run_false_pass_probes(self.packet())
        self.assertEqual(result["verdict"], "PASS")
        self.assertTrue(all(result["probes"].values()))

    def test_model_change_is_blocked(self):
        phases = {"raw": self.phase("raw", 1000, "0"), "engine": self.phase("engine", 400, "0"), "engine_costdoctor": self.phase("engine_costdoctor", 100, "0")}
        phases["engine"]["events"][0]["model"] = "fixture-basic-v1"
        packet = build_three_stage_packet("three", phases, quality_threshold=1.0, rollback={}, context_receipts={}, claim_scope="test")
        self.assertEqual(packet["claim"]["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
