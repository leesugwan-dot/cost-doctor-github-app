from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "universal"))

from costdoctor.benchmark import build_benchmark_packet  # noqa: E402
from costdoctor.canonical import sha256_json, utc_now  # noqa: E402
from costdoctor.detectors import DETECTOR_IDS  # noqa: E402
from costdoctor.pricing import PricingEngine  # noqa: E402
from costdoctor.registry import PricingRegistry  # noqa: E402
from costdoctor.report_validator import validate_user_report  # noqa: E402
from costdoctor.user_report import (  # noqa: E402
    ACTION_KO,
    APPLICATION_STATES,
    DETECTOR_LABEL_KO,
    build_user_report,
    render_user_report_html,
    render_user_summary_markdown,
)
from costdoctor.validator import validate_packet  # noqa: E402


class UserReportContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pricing = PricingEngine(PricingRegistry(ROOT / "universal" / "registry" / "pricing"))

    def binding(self):
        return {
            "goal": "same",
            "input_fingerprint": "1" * 64,
            "quality_criteria": "exact",
            "latency_limit_ms": 100,
            "tool_permissions": [],
            "repetitions": 2,
            "environment_fingerprint": "env",
            "workload_fingerprint": "2" * 64,
            "commit": "a" * 40,
        }

    def event(self, event_id, run_id, tokens, model="fixture-mid-v1", quality=1.0):
        event = {
            "schema": "costdoctor.usage-event.v1",
            "event_id": event_id,
            "workload_id": "report-contract",
            "run_id": run_id,
            "sequence": 0,
            "provider": "generic",
            "model": model,
            "started_at": utc_now(),
            "ended_at": utc_now(),
            "success": quality >= 1.0,
            "error_class": None,
            "usage": {"input_tokens": tokens, "output_tokens": 10, "cached_input_tokens": 0, "cache_write_tokens": 0, "reasoning_tokens": 0, "tool_calls": 0, "call_count": 1, "retry_count": 0},
            "billed_units": {},
            "provider_reported": False,
            "measurement_source": "LOCAL_DETERMINISTIC_ACTUAL_RUN",
            "latency_ms": 1,
            "cache_hit": False,
            "tool_sequence": [],
            "source_binding": {"commit": "a" * 40},
            "environment_fingerprint": "env",
            "workload_fingerprint": "2" * 64,
            "input_fingerprint": "3" * 64,
            "context_fingerprint": "4" * 64,
            "quality_score": quality,
            "metadata": {},
            "batch": False,
        }
        event["event_digest"] = sha256_json(event)
        return event

    def packet(self, after_tokens=100, after_quality=1.0, model="fixture-mid-v1", binding_match=True):
        before = [self.event("b1", "br1", 1000), self.event("b2", "br2", 1000)]
        after = [self.event("a1", "ar1", after_tokens, model, after_quality), self.event("a2", "ar2", after_tokens, model, after_quality)]
        before_prices = [self.pricing.price_event(event) for event in before]
        after_prices = [self.pricing.price_event(event) for event in after]
        before_binding = self.binding()
        after_binding = deepcopy(before_binding)
        if not binding_match:
            after_binding["goal"] = "different"
        rollback = {
            "actual_status": "PASS",
            "baseline_metrics_fingerprint": "x",
            "restored_before_metrics_fingerprint": "x",
            "after_metrics_fingerprint": "y",
            "reapplied_after_metrics_fingerprint": "y",
        }
        return build_benchmark_packet(
            "report-contract",
            before,
            after,
            before_prices,
            after_prices,
            before_binding,
            after_binding,
            1.0,
            rollback,
            [{"detector": "반복 호출", "recommendation": "중복 호출을 합치세요."}],
            {"verdict": "NOT_APPLICABLE"},
            "TEST_FIXTURE_ONLY",
        )

    def bundle(self, packet=None, application_state=None, validation=None):
        packet = packet or self.packet()
        validation = validation or validate_packet(packet)
        report = build_user_report(packet, validation, application_state)
        easy = render_user_report_html(report)
        printable = render_user_report_html(report, printable=True)
        checked = validate_user_report(
            packet,
            validation,
            report,
            easy,
            printable,
            expected_application_state=application_state,
            regenerated_report=build_user_report(packet, validation, application_state),
            regenerated_easy_html=render_user_report_html(report),
            regenerated_print_html=render_user_report_html(report, printable=True),
        )
        return validation, report, easy, printable, checked

    def test_verified_report_has_three_depths_and_six_cards(self):
        _, report, easy, _, checked = self.bundle()
        self.assertEqual(checked["verdict"], "PASS")
        self.assertIn("summary_10_seconds", report)
        self.assertIn("explanation_1_minute", report)
        self.assertIn("details", report)
        self.assertEqual(easy.count('class="card"'), 6)

    def test_verified_savings_and_quality_are_recomputed(self):
        validation, report, _, _, checked = self.bundle()
        self.assertEqual(report["facts"]["verified_savings_usd"], validation["verified_savings_usd"])
        self.assertEqual(report["facts"]["verdict"], "PASS")
        self.assertEqual(report["facts"]["trust_level"], "VERIFIED")
        self.assertEqual(checked["source_recomputation"], "PASS")

    def test_easy_and_print_views_have_identical_facts(self):
        _, _, _, _, checked = self.bundle()
        self.assertEqual(checked["visible_fact_parity"], "PASS")

    def test_same_evidence_regenerates_deterministically(self):
        _, _, _, _, checked = self.bundle()
        self.assertEqual(checked["deterministic_regeneration"], "PASS")

    def test_quality_loss_is_reported_as_failure_not_savings(self):
        _, report, _, _, checked = self.bundle(self.packet(after_quality=0.0))
        self.assertEqual(report["facts"]["verdict"], "FAIL")
        self.assertIsNone(report["facts"]["verified_savings_usd"])
        self.assertEqual(report["facts"]["application_state"], "APPLY_FAILED")
        self.assertEqual(checked["verdict"], "PASS")

    def test_no_cost_reduction_is_not_reported_as_savings(self):
        _, report, _, _, checked = self.bundle(self.packet(after_tokens=1000))
        self.assertEqual(report["facts"]["verdict"], "NO_SAVINGS")
        self.assertIsNone(report["facts"]["verified_savings_usd"])
        self.assertEqual(report["facts"]["application_state"], "ROLLED_BACK")
        self.assertEqual(checked["verdict"], "PASS")

    def test_unknown_price_is_blocked_not_estimated(self):
        validation, report, _, _, checked = self.bundle(self.packet(model="future-model-x"))
        self.assertEqual(validation["verdict"], "BLOCKED")
        self.assertEqual(report["facts"]["verdict"], "BLOCKED")
        self.assertEqual(report["facts"]["trust_level"], "UNKNOWN")
        self.assertIsNone(report["facts"]["verified_savings_usd"])
        self.assertEqual(checked["verdict"], "PASS")

    def test_binding_mismatch_is_visible_as_blocked(self):
        _, report, _, _, checked = self.bundle(self.packet(binding_match=False))
        self.assertEqual(report["facts"]["verdict"], "BLOCKED")
        self.assertEqual(checked["verdict"], "PASS")

    def test_missing_independent_evidence_is_not_certain(self):
        packet = self.packet()
        validation = {"verdict": "NEEDS_EVIDENCE", "verified_savings_usd": None}
        _, report, _, _, checked = self.bundle(packet, validation=validation)
        self.assertEqual(report["facts"]["verdict"], "NEEDS_EVIDENCE")
        self.assertNotIn(report["facts"]["trust_level"], {"VERIFIED", "BILLING_CONFIRMED"})
        self.assertEqual(checked["verdict"], "PASS")

    def test_numeric_report_tamper_is_rejected(self):
        packet = self.packet()
        validation, report, easy, printable, _ = self.bundle(packet)
        report["facts"]["before_cost_usd"] = "999.000000000"
        checked = validate_user_report(packet, validation, report, easy, printable)
        self.assertIn("REPORT_FACT_MISMATCH:before_cost_usd", checked["failures"])

    def test_html_fact_tamper_is_rejected(self):
        packet = self.packet()
        validation, report, easy, printable, _ = self.bundle(packet)
        easy = easy.replace('data-field="verdict">PASS', 'data-field="verdict">FAIL')
        checked = validate_user_report(packet, validation, report, easy, printable)
        self.assertIn("EASY_HTML_FACT_MISMATCH:verdict", checked["failures"])

    def test_sensitive_default_view_is_rejected(self):
        packet = self.packet()
        validation, report, easy, printable, _ = self.bundle(packet)
        easy = easy.replace("</body>", "<p>C:\\private\\benchmark_packet.json</p></body>")
        checked = validate_user_report(packet, validation, report, easy, printable)
        self.assertEqual(checked["user_view_sanitized"], "FAIL")

    def test_all_application_states_are_explicitly_rendered(self):
        packet = self.packet()
        validation = validate_packet(packet)
        for state in APPLICATION_STATES:
            report = build_user_report(packet, validation, state)
            self.assertIn(f'data-field="application_state">{state}', render_user_report_html(report))

    def test_billing_confirmed_cannot_be_invented(self):
        packet = self.packet()
        validation, report, easy, printable, _ = self.bundle(packet)
        report["facts"]["trust_level"] = "BILLING_CONFIRMED"
        easy = easy.replace('data-field="trust_level">VERIFIED', 'data-field="trust_level">BILLING_CONFIRMED')
        printable = printable.replace('data-field="trust_level">VERIFIED', 'data-field="trust_level">BILLING_CONFIRMED')
        checked = validate_user_report(packet, validation, report, easy, printable)
        self.assertIn("BILLING_CONFIRMED_WITHOUT_PROVIDER_EVIDENCE", checked["failures"])

    def test_normal_views_do_not_leak_internal_artifacts(self):
        _, report, easy, printable, checked = self.bundle()
        combined = easy + printable + render_user_summary_markdown(report)
        self.assertNotIn("benchmark_packet.json", combined)
        self.assertNotIn("producer_digest", combined)
        self.assertEqual(checked["user_view_sanitized"], "PASS")

    def test_report_schema_is_valid_json_and_declares_core_contract(self):
        schema = json.loads((ROOT / "universal" / "schemas" / "user-report.v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schema"]["const"], "costdoctor.user-report.v1")
        self.assertIn("facts", schema["required"])

    def test_every_detector_has_easy_korean_copy(self):
        self.assertEqual(set(DETECTOR_IDS), set(DETECTOR_LABEL_KO))
        self.assertEqual(set(DETECTOR_IDS), set(ACTION_KO))
        self.assertTrue(all(any("가" <= char <= "힣" for char in text) for text in DETECTOR_LABEL_KO.values()))
        self.assertTrue(all(any("가" <= char <= "힣" for char in text) for text in ACTION_KO.values()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
