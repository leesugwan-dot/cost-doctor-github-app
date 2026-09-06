from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "universal"))

from costdoctor.adapters import build_adapter  # noqa: E402
from costdoctor.evidence import EvidenceError, UsageImporter, verify_receipt_chain  # noqa: E402
from costdoctor.registry import ModelRegistry, ProviderRegistry  # noqa: E402
from costdoctor.schema import SchemaError  # noqa: E402


class AdapterEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.importer = UsageImporter(
            ModelRegistry(ROOT / "universal" / "registry" / "models"),
            ProviderRegistry(ROOT / "universal" / "registry" / "providers"),
        )
        cls.context = {
            "workload_id": "test",
            "run_id": "run",
            "provider": "generic",
            "model": "fixture-mid",
            "source_binding": {"commit": "a" * 40},
            "environment_fingerprint": "test-env",
            "workload_fingerprint": "b" * 64,
        }

    def raw(self, event_id="e1", sequence=0):
        return {
            "event_id": event_id,
            "sequence": sequence,
            "started_at": "2026-09-06T00:00:00+00:00",
            "ended_at": "2026-09-06T00:00:01+00:00",
            "success": True,
            "usage": {"input_tokens": 10, "output_tokens": 2},
            "latency_ms": 1,
            "quality_score": 1.0,
        }

    def test_generic_normalization_and_receipt_chain(self):
        evidence = self.importer.normalize_records([self.raw()], self.context)
        self.assertEqual(evidence["events"][0]["model"], "fixture-mid-v1")
        self.assertTrue(verify_receipt_chain(evidence))

    def test_duplicate_event_is_rejected(self):
        with self.assertRaisesRegex(EvidenceError, "DUPLICATE_EVENT"):
            self.importer.normalize_records([self.raw(), self.raw()], self.context)

    def test_out_of_order_event_is_rejected(self):
        with self.assertRaisesRegex(EvidenceError, "OUT_OF_ORDER"):
            self.importer.normalize_records([self.raw("e1", 1), self.raw("e2", 0)], self.context)

    def test_sensitive_field_is_rejected(self):
        raw = self.raw()
        raw["prompt"] = "do not store"
        with self.assertRaisesRegex(SchemaError, "SENSITIVE_FIELD"):
            self.importer.normalize_records([raw], self.context)

    def test_secret_pattern_is_rejected(self):
        raw = self.raw()
        raw["metadata"] = {"note": "sk-" + "a" * 32}
        with self.assertRaisesRegex(SchemaError, "SECRET_PATTERN"):
            self.importer.normalize_records([raw], self.context)

    def test_tampered_receipt_chain_is_rejected(self):
        evidence = self.importer.normalize_records([self.raw()], self.context)
        evidence["events"][0]["usage"]["input_tokens"] += 1
        self.assertFalse(verify_receipt_chain(evidence))

    def test_openai_adapter_contract(self):
        usage = build_adapter("openai_v1").normalize_usage(
            {"usage": {"prompt_tokens": 20, "completion_tokens": 5, "prompt_tokens_details": {"cached_tokens": 4}, "completion_tokens_details": {"reasoning_tokens": 2}}}
        )
        self.assertEqual((usage["input_tokens"], usage["cached_input_tokens"], usage["reasoning_tokens"]), (16, 4, 2))

    def test_anthropic_adapter_contract(self):
        usage = build_adapter("anthropic_v1").normalize_usage(
            {"usage": {"input_tokens": 20, "output_tokens": 5, "cache_read_input_tokens": 4, "cache_creation_input_tokens": 3}}
        )
        self.assertEqual((usage["cached_input_tokens"], usage["cache_write_tokens"]), (4, 3))

    def test_gemini_adapter_contract(self):
        usage = build_adapter("gemini_v1").normalize_usage(
            {"usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 5, "cachedContentTokenCount": 4, "thoughtsTokenCount": 2}}
        )
        self.assertEqual((usage["input_tokens"], usage["reasoning_tokens"]), (16, 2))

    def test_ollama_adapter_contract(self):
        usage = build_adapter("ollama_v1").normalize_usage({"prompt_eval_count": 20, "eval_count": 5})
        self.assertEqual((usage["input_tokens"], usage["output_tokens"]), (20, 5))

    def test_agnes_adapter_is_offline(self):
        self.assertEqual(build_adapter("agnes_v1").health_check()["network_calls"], 0)

    def test_unknown_adapter_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "PROVIDER_ADAPTER_UNKNOWN"):
            build_adapter("unknown")


if __name__ == "__main__":
    unittest.main(verbosity=2)
