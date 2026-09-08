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

    def test_english_is_default_and_korean_route_is_reciprocal(self):
        landing = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        korean = (ROOT / "docs" / "ko" / "index.html").read_text(encoding="utf-8")
        self.assertLess(landing.index('value="en"'), landing.index('value="ko"'))
        self.assertIn('hreflang="ko"', landing)
        self.assertIn('hreflang="en"', korean)
        self.assertIn('hreflang="x-default"', korean)
        self.assertIn('rel="canonical"', korean)

    def test_seo_and_social_contract_has_no_fake_claims(self):
        landing = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertIn('application/ld+json', landing)
        self.assertIn('og:image', landing)
        self.assertNotIn('aggregateRating', landing)
        self.assertNotIn('"offers"', landing)
        self.assertTrue((ROOT / "docs" / "social-preview.svg").exists())

    def test_guides_and_sitemap_are_english_first(self):
        sitemap = (ROOT / "docs" / "sitemap.xml").read_text(encoding="utf-8")
        self.assertIn("/ko/", sitemap)
        for slug in (
            "llm-cost-optimization.md",
            "llm-retry-cost.md",
            "prompt-cache-cost.md",
            "token-context-cost.md",
            "static-analysis-boundary.md",
        ):
            self.assertIn("/guides/" + slug, sitemap)
            guide = ROOT / "docs" / "guides" / slug
            self.assertTrue(guide.exists())
            self.assertIn("UNKNOWN", guide.read_text(encoding="utf-8"))

    def test_readmes_and_launch_kit_have_english_entry(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        entry = (ROOT / "costdoctor-entry" / "README.md").read_text(encoding="utf-8")
        launch = (ROOT / "docs" / "LAUNCH_KIT.md").read_text(encoding="utf-8")
        self.assertLess(readme.index("Free, read-only AI/LLM cost review"), readme.index("한국어"))
        self.assertIn("English first", entry)
        self.assertLess(launch.index("English-first Launch Kit"), launch.index("한국어 보조 문안"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
