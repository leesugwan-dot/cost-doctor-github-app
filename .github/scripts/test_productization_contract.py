#!/usr/bin/env python3
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]


class ProductizationContractTests(unittest.TestCase):
    def test_quick_scan_contract_is_secretless_and_fallback_bound(self):
        data = json.loads((ROOT / "productization" / "quick_scan_contract.json").read_text(encoding="utf-8"))
        self.assertTrue(data["input"]["one_public_github_url"])
        self.assertEqual(data["input"]["allowed_host"], "github.com")
        self.assertEqual(data["safety"]["model_api_calls"], 0)
        self.assertFalse(data["trusted_dispatch"]["client_credentials"])
        self.assertTrue(data["fallback"]["preserved"])

    def test_usage_contract_has_owner_external_and_funnel_rules(self):
        data = json.loads((ROOT / "productization" / "usage_evidence_contract.json").read_text(encoding="utf-8"))
        self.assertIn("OWNER_TEST", data["categories"])
        self.assertIn("CONFIRMED_EXTERNAL_ACTOR", data["categories"])
        self.assertTrue(data["rules"]["owner_tests_excluded_from_external"])
        self.assertIn("result_pass", data["funnel"])

    def test_landing_has_one_url_form_and_safe_fallback(self):
        text = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-quick-scan-form', text)
        self.assertIn('data-repository-url', text)
        self.assertIn('data-result-language', text)
        self.assertIn('quick-scan.js', text)
        self.assertIn('Open fallback Issue Form', text)
        self.assertIn('canonical', text)

    def test_landing_script_has_allowlist_and_no_credentials(self):
        text = (ROOT / "docs" / "quick-scan.js").read_text(encoding="utf-8")
        self.assertIn('parsed.hostname.toLowerCase() !== "github.com"', text)
        self.assertIn('parsed.protocol !== "https:"', text)
        self.assertIn('public-scan.yml', text)
        self.assertNotIn("GITHUB_TOKEN", text)
        self.assertNotIn("api.github.com", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
