#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("public_scan_entry", HERE / "public_scan_entry.py")
entry = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(entry)


class PublicScanOwnerBypassTests(unittest.TestCase):
    def test_repository_owner_is_exempt_case_insensitively(self):
        self.assertTrue(entry.is_repository_owner("Owner/repo", "owner"))
        self.assertTrue(entry.is_repository_owner("owner/repo", "OWNER"))

    def test_non_owner_is_not_exempt(self):
        self.assertFalse(entry.is_repository_owner("owner/repo", "other-user"))
        self.assertFalse(entry.is_repository_owner("owner/repo", ""))
        self.assertFalse(entry.is_repository_owner("malformed", "owner"))

    def test_owner_bypass_does_not_call_base_limiter(self):
        calls = []
        old = entry._BASE_ENFORCE_RATE_LIMIT
        try:
            def fail_if_called(*args, **kwargs):
                calls.append((args, kwargs))
                raise AssertionError("base limiter must not be called for repository owner")
            entry._BASE_ENFORCE_RATE_LIMIT = fail_if_called
            self.assertIsNone(entry.enforce_rate_limit("owner/repo", "owner", 99, "token"))
            self.assertEqual(calls, [])
        finally:
            entry._BASE_ENFORCE_RATE_LIMIT = old

    def test_non_owner_still_uses_existing_rate_limiter(self):
        calls = []
        old = entry._BASE_ENFORCE_RATE_LIMIT
        try:
            def fake_base(repository, user, issue_number, token):
                calls.append((repository, user, issue_number, token))
                return "checked"
            entry._BASE_ENFORCE_RATE_LIMIT = fake_base
            result = entry.enforce_rate_limit("owner/repo", "external-user", 7, "token")
            self.assertEqual(result, "checked")
            self.assertEqual(calls, [("owner/repo", "external-user", 7, "token")])
        finally:
            entry._BASE_ENFORCE_RATE_LIMIT = old


if __name__ == "__main__":
    unittest.main(verbosity=2)
