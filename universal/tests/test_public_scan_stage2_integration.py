import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_SCAN = ROOT / ".github" / "scripts" / "public_scan.py"


class PublicScanStage2IntegrationTests(unittest.TestCase):
    def test_public_scan_reuses_checkout_and_posts_one_combined_comment(self):
        text = PUBLIC_SCAN.read_text(encoding="utf-8")
        self.assertIn("run_universal_stage2", text)
        self.assertIn("target_dir, result_dir", text)
        self.assertIn("stage2_verified_savings_report.md", text)
        self.assertIn("markdown = markdown +", text)
        self.assertEqual(text.count("post_comment(repository, issue_number, token, markdown)"), 1)
        self.assertIn("close_and_lock(repository, issue_number, token)", text)

    def test_public_scan_has_no_fixture_specific_provider_logic(self):
        text = PUBLIC_SCAN.read_text(encoding="utf-8")
        for forbidden in ("active-project-reliability-demo", "UPSTAGE_API_KEY", "solar-pro3", "api.upstage.ai"):
            self.assertNotIn(forbidden, text)

    def test_advanced_verified_workflow_is_preserved(self):
        self.assertTrue((ROOT / ".github" / "workflows" / "public-verified-savings.yml").is_file())

    def test_stage2_report_script_is_importable(self):
        spec = importlib.util.spec_from_file_location("public_scan", PUBLIC_SCAN)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        self.assertTrue(callable(module.run_universal_stage2))


if __name__ == "__main__":
    unittest.main()
