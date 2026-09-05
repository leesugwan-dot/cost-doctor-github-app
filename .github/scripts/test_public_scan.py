#!/usr/bin/env python3
import importlib.util
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
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

    def test_public_result_has_no_filename_field(self):
        report = {
            "verdict": "SCAN_COMPLETE",
            "coverage": {"analyzed_files": 3, "analyzed_bytes": 123},
            "findings": [
                {"rule": "MODEL_CALL", "title": "모델 호출 후보", "signal_count": 2},
                {"rule": "CACHE_SIGNAL", "title": "캐시 사용 후보", "signal_count": 1},
            ],
        }
        meta = {"language": "Python"}
        text = mod.format_result(
            report, "a/b", meta, "ko",
            "https://github.com/x/y/issues/1",
            "https://github.com/x/y/actions/runs/1",
        )
        self.assertIn("실제 비용·토큰 절감: UNKNOWN", text)
        self.assertNotIn("filename", text.lower())
        self.assertNotIn("파일명:", text)

    def test_english_result_keeps_unknown_claim_boundary(self):
        report = {
            "verdict": "SCAN_COMPLETE",
            "coverage": {"analyzed_files": 1, "analyzed_bytes": 10},
            "findings": [{"rule": "MODEL_CALL", "title": "x", "signal_count": 1}],
        }
        text = mod.format_result(
            report, "a/b", {"language": "JavaScript"}, "en",
            "https://github.com/x/y/issues/1",
            "https://github.com/x/y/actions/runs/1",
        )
        self.assertIn("Actual token/cost savings: UNKNOWN", text)
        self.assertIn("No target-project code was executed", text)

    def test_error_message_is_bounded_and_retryable(self):
        text = mod.friendly_error("URL_INVALID", "ko", "https://github.com/x/y/issues/new")
        self.assertIn("URL_INVALID", text)
        self.assertIn("새 진단 시작", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
