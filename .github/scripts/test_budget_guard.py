#!/usr/bin/env python3
import importlib.util
import pathlib
import unittest
from decimal import Decimal

HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("budget_guard", HERE / "budget_guard.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class BudgetGuardTests(unittest.TestCase):
    def test_allows_within_approved_limit(self):
        r = mod.evaluate(Decimal("5"), Decimal("1.25"), Decimal("2"))
        self.assertEqual(r["status"], "ALLOW_WITHIN_APPROVED_BUDGET")
        self.assertEqual(r["remaining_after_max_usd"], "1.75")

    def test_blocks_over_limit(self):
        r = mod.evaluate(Decimal("5"), Decimal("4"), Decimal("1.01"))
        self.assertEqual(r["status"], "BLOCK_BUDGET")
        self.assertEqual(r["code"], "BUDGET_LIMIT_EXCEEDED")

    def test_blocks_without_positive_approval(self):
        r = mod.evaluate(Decimal("0"), Decimal("0"), Decimal("0"))
        self.assertEqual(r["code"], "BUDGET_NOT_APPROVED")

    def test_rejects_negative_or_invalid_money(self):
        for value in ("-1", "nan", "inf", "abc"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    mod.money(value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
