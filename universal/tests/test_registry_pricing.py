from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "universal"))

from costdoctor.pricing import PricingEngine  # noqa: E402
from costdoctor.registry import ModelRegistry, PricingRegistry  # noqa: E402


class RegistryPricingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = ModelRegistry(ROOT / "universal" / "registry" / "models")
        cls.registry = PricingRegistry(ROOT / "universal" / "registry" / "pricing")
        cls.engine = PricingEngine(cls.registry)

    def event(self, model="fixture-mid-v1", provider="generic", **usage):
        return {
            "event_id": "e-1",
            "provider": provider,
            "model": model,
            "started_at": "2026-09-06T12:00:00+00:00",
            "usage": {"input_tokens": 1000, "output_tokens": 100, **usage},
            "billed_units": {},
            "batch": False,
        }

    def test_alias_resolves_to_canonical_model(self):
        self.assertEqual(self.models.canonical_id("fixture-mid"), "fixture-mid-v1")

    def test_unknown_model_is_tolerated(self):
        self.assertIsNone(self.models.resolve("not-in-registry"))
        self.assertEqual(self.models.canonical_id("not-in-registry"), "not-in-registry")

    def test_deprecated_model_is_not_active(self):
        self.assertNotIn("fixture-retired-v0", {row["canonical_id"] for row in self.models.active_rows()})

    def test_future_model_is_registry_data(self):
        self.assertEqual(self.models.resolve("future-x-preview")["status"], "preview")

    def test_effective_dated_price_is_selected(self):
        row = self.registry.select("generic", "fixture-mid-v1", "2026-09-06T12:00:00+00:00")
        self.assertEqual(row["price_version"], "fixture-2026-09-06")
        self.assertEqual(len(row["snapshot_digest"]), 64)

    def test_unknown_price_fails_closed(self):
        result = self.engine.price_event(self.event(model="future-model-x"))
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIsNone(result["cost_usd"])

    def test_cached_and_reasoning_tokens_are_priced(self):
        result = self.engine.price_event(
            self.event(input_tokens=0, cached_input_tokens=1000, reasoning_tokens=1000)
        )
        self.assertEqual(result["status"], "MEASURED_PRICE_APPLIED")
        self.assertEqual(result["cost_usd"], "0.002800000")

    def test_batch_discount_is_applied(self):
        event = self.event(input_tokens=1000, output_tokens=0)
        event["batch"] = True
        self.assertEqual(self.engine.price_event(event)["cost_usd"], "0.001000000")

    def test_unknown_custom_unit_fails_closed(self):
        event = self.event(input_tokens=0, output_tokens=0)
        event["billed_units"] = {"gpu_seconds": 1}
        self.assertEqual(self.engine.price_event(event)["status"], "UNKNOWN")

    def test_local_price_is_explicit_zero(self):
        result = self.engine.price_event(self.event(model="local-fixture-v1", provider="ollama"))
        self.assertEqual(result["status"], "MEASURED_PRICE_APPLIED")
        self.assertEqual(result["cost_usd"], "0.000000000")

    def test_price_change_requires_registry_row_only(self):
        row = deepcopy(self.registry.select("generic", "fixture-mid-v1", "2026-09-06T12:00:00+00:00"))
        row.pop("snapshot_digest")
        row["effective_from"] = "2026-09-06T00:00:00+00:00"
        row["price_version"] = "data-only-change"
        row["unit_rates_usd"]["input_tokens"] = 3
        changed = PricingEngine(self.registry.with_rows([row])).price_event(self.event(output_tokens=0))
        self.assertEqual(changed["cost_usd"], "0.003000000")


if __name__ == "__main__":
    unittest.main(verbosity=2)
