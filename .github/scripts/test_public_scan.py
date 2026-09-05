#!/usr/bin/env python3
import importlib.util
import json
import pathlib
import re
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPEC = importlib.util.spec_from_file_location("public_scan", HERE / "public_scan.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class PublicScanTests(unittest.TestCase):
    def test_normalize_root_url(self):
        self.assertEqual(mod.normalize_repo("https://github.com/openai/openai"), "openai/openai")
        self.assertEqual(mod.normalize_repo("https://github.com/openai/openai.git"), "openai/openai")

    def test_normalize_nested_url(self):
        self.assertEqual(
            mod.normalize_repo("https://github.com/openai/openai/tree/main?x=1#readme"),
            "openai/openai",
        )

    def test_normalize_without_scheme(self):
        self.assertEqual(mod.normalize_repo("github.com/openai/openai"), "openai/openai")

    def test_reject_non_github(self):
        with self.assertRaises(ValueError):
            mod.normalize_repo("https://example.com/openai/openai")
        with self.assertRaises(ValueError):
            mod.normalize_repo("http://github.com/openai/openai")

    def test_reject_credentials(self):
        with self.assertRaises(ValueError):
            mod.normalize_repo("https://user:pass@github.com/openai/openai")

    def test_extract_and_language(self):
        body = """### GitHub 저장소 주소

https://github.com/openai/openai

### 결과 언어 / Result language

English

### 확인

- [x] 이 저장소가 공개 저장소이며 진단 결과가 공개 GitHub 이슈에 표시되는 것에 동의합니다.
"""
        self.assertEqual(mod.extract_field(body, mod.URL_HEADING), "https://github.com/openai/openai")
        self.assertEqual(mod.parse_language(body), "en")
        self.assertTrue(mod.confirmation_present(body))

    def test_confirmation_is_required(self):
        body = "### GitHub 저장소 주소\n\nhttps://github.com/a/b\n"
        self.assertFalse(mod.confirmation_present(body))

    def test_default_language_is_korean(self):
        self.assertEqual(mod.parse_language("### GitHub 저장소 주소\n\nhttps://github.com/a/b\n"), "ko")

    def test_rate_limit_fails_closed(self):
        old_api = mod.api
        try:
            mod.api = lambda *args, **kwargs: [
                {"number": n, "title": f"{mod.TITLE_PREFIX} test-{n}"} for n in range(1, 6)
            ]
            with self.assertRaisesRegex(ValueError, "RATE_LIMITED"):
                mod.enforce_rate_limit("owner/repo", "user", 99, "token")
        finally:
            mod.api = old_api

    def test_rate_limit_allows_below_cap(self):
        old_api = mod.api
        try:
            mod.api = lambda *args, **kwargs: [
                {"number": 1, "title": f"{mod.TITLE_PREFIX} test"},
                {"number": 2, "title": "[Bug] unrelated"},
            ]
            mod.enforce_rate_limit("owner/repo", "user", 99, "token")
        finally:
            mod.api = old_api

    def test_private_repository_is_rejected(self):
        old_api = mod.api
        try:
            mod.api = lambda *args, **kwargs: {"private": True}
            with self.assertRaisesRegex(ValueError, "PUBLIC_REPO_REQUIRED"):
                mod.get_target_metadata("owner/repo", "token")
        finally:
            mod.api = old_api

    def sample_report(self):
        return {
            "verdict": "SCAN_COMPLETE",
            "coverage": {"analyzed_files": 3, "analyzed_bytes": 123},
            "findings": [
                {"rule": "MODEL_CALL", "title": "모델 호출 후보", "signal_count": 2},
                {"rule": "CACHE_SIGNAL", "title": "캐시 사용 후보", "signal_count": 1},
            ],
            "privacy": {"raw_source_output": False, "filenames_output": False},
        }

    def sample_meta(self):
        return {
            "head": "a" * 40,
            "default_branch": "main",
            "language": "Python",
            "archived": False,
            "fork": False,
        }

    def test_receipt_is_deterministic_for_same_inputs(self):
        report = self.sample_report()
        meta = self.sample_meta()
        args = (
            report, "a/b", meta,
            "https://github.com/x/y/issues/1",
            "https://github.com/x/y/actions/runs/1",
            "b" * 40,
        )
        r1 = mod.build_receipt(*args, generated_at="2026-09-06T00:00:00Z")
        r2 = mod.build_receipt(*args, generated_at="2026-09-06T00:00:00Z")
        self.assertEqual(r1, r2)
        self.assertRegex(r1["receipt_sha256"], r"^[a-f0-9]{64}$")
        self.assertEqual(r1["target"]["head"], "a" * 40)
        self.assertEqual(r1["costdoctor"]["head"], "b" * 40)
        self.assertFalse(r1["privacy"]["operator_personal_pc_used"])
        self.assertFalse(r1["claims"]["actual_savings_verified"])

    def test_public_output_contains_only_sanitized_result_and_receipt(self):
        report = self.sample_report()
        receipt = mod.build_receipt(
            report, "a/b", self.sample_meta(),
            "https://github.com/x/y/issues/1",
            "https://github.com/x/y/actions/runs/1",
            "b" * 40,
            generated_at="2026-09-06T00:00:00Z",
        )
        markdown = mod.format_result(
            report, "a/b", self.sample_meta(), "ko",
            "https://github.com/x/y/issues/1",
            "https://github.com/x/y/actions/runs/1",
            receipt=receipt,
        )
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "out"
            mod.write_public_output(out, markdown, receipt)
            self.assertEqual(sorted(p.name for p in out.iterdir()), ["receipt.json", "result.md"])
            loaded = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(loaded["receipt_sha256"], receipt["receipt_sha256"])
            combined = (out / "result.md").read_text(encoding="utf-8") + (out / "receipt.json").read_text(encoding="utf-8")
            self.assertNotIn("private key", combined.lower())
            self.assertNotIn("api_key=", combined.lower())

    def test_public_result_has_no_filename_field(self):
        report = self.sample_report()
        receipt = mod.build_receipt(
            report, "a/b", self.sample_meta(),
            "https://github.com/x/y/issues/1",
            "https://github.com/x/y/actions/runs/1",
            "b" * 40,
            generated_at="2026-09-06T00:00:00Z",
        )
        text = mod.format_result(
            report, "a/b", self.sample_meta(), "ko",
            "https://github.com/x/y/issues/1",
            "https://github.com/x/y/actions/runs/1",
            receipt=receipt,
        )
        self.assertIn("실제 비용·토큰 절감: UNKNOWN", text)
        self.assertIn("검증 영수증", text)
        self.assertNotIn("filename", text.lower())
        self.assertNotIn("파일명:", text)

    def test_english_result_keeps_unknown_claim_boundary(self):
        report = self.sample_report()
        text = mod.format_result(
            report, "a/b", self.sample_meta(), "en",
            "https://github.com/x/y/issues/1",
            "https://github.com/x/y/actions/runs/1",
        )
        self.assertIn("Actual token/cost savings: UNKNOWN", text)
        self.assertIn("No target-project code was executed", text)

    def test_error_message_is_bounded_and_retryable(self):
        text = mod.friendly_error("URL_INVALID", "ko", "https://github.com/x/y/issues/new")
        self.assertIn("URL_INVALID", text)
        self.assertIn("새 진단 시작", text)

    def test_private_selfscan_template_keeps_read_only_boundary(self):
        text = (ROOT / "costdoctor-entry" / "private-repo-selfscan.yml").read_text(encoding="utf-8")
        self.assertIn("contents: read", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("submodules: false", text)
        self.assertIn("lfs: false", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("pull-requests: write", text)
        self.assertNotIn("pull_requests: write", text)
        refs = re.findall(r"uses:\s*leesugwan-dot/cost-doctor-github-app/costdoctor-entry@([a-f0-9]+)", text)
        self.assertEqual(len(refs), 1)
        self.assertRegex(refs[0], r"^[a-f0-9]{40}$")

    def test_public_workflow_uploads_only_sanitized_generated_output(self):
        text = (ROOT / ".github" / "workflows" / "public-scan.yml").read_text(encoding="utf-8")
        self.assertIn("steps.scan.outputs.public-output-dir", text)
        self.assertIn("retention-days: 1", text)
        self.assertIn("issues: write", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("pull_request_target", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
