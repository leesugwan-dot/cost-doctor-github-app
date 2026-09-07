import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("public_scan_r4", HERE / "public_scan.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PublicScanR4Tests(unittest.TestCase):
    def test_status_comment_can_be_replaced_in_place(self):
        calls = []
        old = MODULE.api
        try:
            def fake_api(method, url, token, payload=None):
                calls.append((method, url, payload))
                return {"id": 42} if method == "POST" else {"id": 42, "body": payload["body"]}
            MODULE.api = fake_api
            created = MODULE.post_comment("owner/repo", 7, "token", "starting")
            updated = MODULE.update_comment("owner/repo", created["id"], "token", "final")
        finally:
            MODULE.api = old
        self.assertEqual([item[0] for item in calls], ["POST", "PATCH"])
        self.assertIn("/issues/comments/42", calls[1][1])
        self.assertEqual(updated["body"], "final")

    def test_receipt_records_partial_stage2_status(self):
        report = {"verdict": "SCAN_COMPLETE", "coverage": {"analyzed_files": 1, "analyzed_bytes": 10}, "findings": []}
        meta = {"head": "a" * 40, "default_branch": "main", "language": "Python", "archived": False, "fork": False}
        receipt = MODULE.build_receipt(report, "owner/repo", meta, "https://github.com/o/r/issues/1", "https://github.com/o/r/actions/runs/1", "b" * 40, generated_at="2026-09-08T00:00:00Z", stage2_status="PARTIAL_STAGE1_ONLY")
        self.assertEqual(receipt["scan"]["stage2_status"], "PARTIAL_STAGE1_ONLY")
        self.assertEqual(receipt["scan"]["stage2_trust_level"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main(verbosity=2)
