from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "universal"))

from costdoctor.capsules import build_capsule, verify_capsule  # noqa: E402
from costdoctor.context_optimizer import ContextOptimizationError, context_size_receipt, extract_facts, optimize_context, resolve_authority  # noqa: E402


class ContextOptimizerTests(unittest.TestCase):
    def task(self):
        return {"task_id": "context-test", "objective": "retain required facts", "acceptance": ["facts retained"], "allowed_scope": ["universal"], "forbidden_scope": ["network"], "target_files": ["universal/README.md"], "output_contract": "evidence only", "required_fact_ids": ["goal", "boundary"]}

    def state(self):
        return {"completed": [], "pending": ["context"], "current_authority": "current", "current_version": "1", "blockers": [], "next_action": "package"}

    def entries(self):
        return [
            {"id": "goal-old", "fact_id": "goal", "authority_key": "goal", "version": 1, "value": "old", "required": True, "priority": 100},
            {"id": "goal-current", "fact_id": "goal", "authority_key": "goal", "version": 2, "value": "current", "required": True, "priority": 100},
            {"id": "boundary", "fact_id": "boundary", "value": "no network", "required": True, "priority": 90},
            {"id": "history", "fact_id": "history", "value": "x" * 5000, "required": False, "priority": 1},
            {"id": "proof", "fact_id": "proof", "kind": "evidence", "pointer": {"sha256": "a" * 64, "locator": "evidence/summary.json", "count": 3}, "priority": 80},
        ]

    def test_deterministic_authority_delta_and_loss_guard(self):
        first = optimize_context(self.task(), self.state(), self.entries(), 400)
        second = optimize_context(self.task(), self.state(), self.entries(), 400)
        self.assertEqual(first, second)
        self.assertTrue(verify_capsule(first))
        self.assertEqual(first["retention_check"]["verdict"], "PASS")
        self.assertIn("goal-old", first["authority_resolution"]["superseded_ids"])
        self.assertNotIn("history", {row["id"] for row in first["selected_context"]})
        self.assertNotIn("value", next(row for row in first["selected_context"] if row["id"] == "proof"))
        unchanged = optimize_context(self.task(), self.state(), self.entries(), 400, previous_context=first)
        self.assertEqual(unchanged["delta"]["changed_ids"], [])

    def test_required_fact_budget_failure(self):
        with self.assertRaisesRegex(ContextOptimizationError, "LOSS_GUARD"):
            optimize_context(self.task(), self.state(), self.entries(), 1)

    def test_fact_extraction_and_authority_are_explicit(self):
        facts = extract_facts(self.entries(), ["boundary"])
        self.assertTrue(next(row for row in facts if row["fact_id"] == "boundary")["hard_fact"])
        authority = resolve_authority(facts)
        self.assertIn("goal-old", authority["superseded_ids"])

    def test_exact_tokenizer_grade_is_not_byte_claim(self):
        packet = optimize_context(self.task(), self.state(), self.entries(), 500, tokenizer=lambda value: len(value.split()))
        self.assertEqual(packet["token_budget"]["measurement_grade"], "EXACT_TOKENIZER")
        receipt = context_size_receipt(self.entries(), packet)
        self.assertEqual(receipt["measurement_grade"], "BYTE_CONTEXT_ONLY")
        self.assertFalse(receipt["token_savings_claimed"])

    def test_all_six_capsule_contracts(self):
        fixtures = {
            "task": {key: [] if key in {"acceptance", "allowed_scope", "forbidden_scope", "target_files"} else "x" for key in ("task_id", "objective", "acceptance", "allowed_scope", "forbidden_scope", "target_files", "output_contract")},
            "state": {"completed": [], "pending": [], "current_authority": "x", "current_version": "1", "blockers": [], "next_action": "x"},
            "context": {"required_facts": [], "selected_context": [], "omitted_context_reason": {}, "token_budget": {}, "retention_check": {}},
            "evidence": {"run_id": "x", "workload_id": "x", "metrics": {}, "quality": {}, "errors": [], "hashes": {}, "pointers": [], "verifier_result": {}},
            "delta": {"changed_facts": [], "changed_files": [], "changed_decisions": [], "invalidated_evidence": [], "new_requirements": []},
            "usage": {"provider": "x", "model": "x", "input": 0, "cached": 0, "output": 0, "reasoning": 0, "calls": 0, "retries": 0, "cost": None, "measurement_grade": "UNKNOWN"},
        }
        self.assertTrue(all(verify_capsule(build_capsule(kind, payload)) for kind, payload in fixtures.items()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
