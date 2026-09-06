import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "universal" / "scripts" / "run_provider_actual_abc.py"
MODULE_SPEC = importlib.util.spec_from_file_location("provider_actual_runner", SCRIPT)
runner = importlib.util.module_from_spec(MODULE_SPEC)
assert MODULE_SPEC.loader is not None
MODULE_SPEC.loader.exec_module(runner)


class ProviderActualTests(unittest.TestCase):
    def setUp(self):
        self.spec = runner.load_spec(ROOT / "universal" / "workloads" / "provider-actual.v1.json")
        self.pricing = runner.PricingRegistry(ROOT / "universal" / "registry" / "pricing")

    def test_registry_only_model_and_official_price(self):
        models = runner.ModelRegistry(ROOT / "universal" / "registry" / "models")
        row = models.resolve("gpt-5.6-luna")
        self.assertEqual(row["provider"], "openai")
        price = runner._rate_row(self.pricing, "openai", "gpt-5.6-luna")
        self.assertEqual(price["price_grade"], "PROVIDER_PUBLISHED")
        self.assertEqual(price["unit_rates_usd"]["input_tokens"], 0.20)
        self.assertEqual(price["unit_rates_usd"]["cached_input_tokens"], 0.02)
        self.assertEqual(price["unit_rates_usd"]["output_tokens"], 1.20)

    def test_preflight_is_bounded_and_contains_no_raw_prompt(self):
        forecast = runner.conservative_forecast(self.spec, self.pricing)
        self.assertEqual(forecast["planned_calls"], 40)
        self.assertLessEqual(float(forecast["forecast_upper_bound_usd"]), float(runner.HARD_MAX_SPEND_USD))
        serialized = json.dumps(forecast)
        self.assertNotIn("Authoritative instruction", serialized)
        self.assertNotIn("public_fixture", serialized)

    def test_request_uses_privacy_and_output_controls(self):
        request = runner.build_request(
            self.spec,
            self.spec["workloads"][0],
            self.spec["workloads"][0]["items"][0],
            "engine_costdoctor",
            "cache-key",
        )
        self.assertFalse(request["store"])
        self.assertEqual(request["max_output_tokens"], 16)
        self.assertEqual(request["reasoning"]["effort"], "none")
        self.assertEqual(request["text"]["verbosity"], "low")

    def test_integer_parser_rejects_explanations(self):
        good = {"output": [{"content": [{"type": "output_text", "text": " 19\n"}]}]}
        bad = {"output": [{"content": [{"type": "output_text", "text": "The answer is 19"}]}]}
        self.assertEqual(runner.parse_integer(good), 19)
        self.assertIsNone(runner.parse_integer(bad))

    def test_two_fresh_provider_rounds_with_mocked_transport(self):
        calls = []

        def transport(payload, api_key, endpoint):
            self.assertEqual(api_key, "test-key-not-a-secret-pattern")
            self.assertEqual(endpoint, "https://api.openai.com/v1/responses")
            calls.append(payload)
            capsule = json.loads(payload["input"])
            fixture = capsule["public_fixture"]
            if isinstance(fixture, list):
                answer = sum(fixture)
            else:
                answer = len(fixture.split())
            input_tokens = max(1, len(payload["input"].encode("utf-8")) // 4)
            return (
                {
                    "id": f"resp_mock_{len(calls)}",
                    "status": "completed",
                    "model": "gpt-5.6-luna",
                    "service_tier": "default",
                    "usage": {
                        "input_tokens": input_tokens,
                        "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                        "output_tokens": 1,
                        "output_tokens_details": {"reasoning_tokens": 0},
                        "total_tokens": input_tokens + 1,
                    },
                    "output": [{"type": "message", "content": [{"type": "output_text", "text": str(answer)}]}],
                },
                2.0,
            )

        result = runner.execute_all(self.spec, "commit-for-test", "test-key-not-a-secret-pattern", transport)
        self.assertEqual(len(calls), 40)
        diagnostics = [
            {
                "validation": item["independent_validation"]["failures"],
                "provider_actual": item["independent_validation"]["provider_actual_claim"],
                "false_pass": item["false_pass"],
                "claim": item["packet"]["claim"],
                "rollback": item["rollback"]["actual_status"],
            }
            for round_row in result["rounds"]
            for item in round_row["workloads"]
        ]
        self.assertEqual(result["provider_authenticated_verdict"], "PASS", diagnostics)
        self.assertTrue(result["fresh_binding_match"])
        self.assertFalse(result["privacy"]["secret_stored"])
        self.assertNotIn("test-key-not-a-secret-pattern", json.dumps(result))
        for round_row in result["rounds"]:
            for item in round_row["workloads"]:
                self.assertTrue(item["independent_validation"]["provider_actual_claim"])
                self.assertEqual(item["rollback"]["actual_status"], "PASS")
                self.assertEqual(item["false_pass"]["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
