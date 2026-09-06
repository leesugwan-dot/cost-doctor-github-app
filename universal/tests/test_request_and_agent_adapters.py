from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "universal"))

from costdoctor.adapters import build_adapter  # noqa: E402
from costdoctor.capsules import build_capsule  # noqa: E402
from costdoctor.coding_agents import CodingAgentRegistry, build_coding_agent_packet, build_repo_map, collect_coding_agent_usage  # noqa: E402
from costdoctor.context_optimizer import optimize_context  # noqa: E402
from costdoctor.cost_router import choose_execution_route  # noqa: E402
from costdoctor.measurement import classify_measurement  # noqa: E402
from costdoctor.request_adapters import build_llm_request  # noqa: E402


class RequestAndCodingAgentTests(unittest.TestCase):
    def test_current_openai_responses_usage_shape(self):
        usage = build_adapter("openai_v1").normalize_usage({"usage": {"input_tokens": 100, "input_tokens_details": {"cached_tokens": 20, "cache_write_tokens": 10}, "output_tokens": 40, "output_tokens_details": {"reasoning_tokens": 15}}})
        self.assertEqual(usage, {"input_tokens": 70, "output_tokens": 25, "cached_input_tokens": 20, "cache_write_tokens": 10, "reasoning_tokens": 15, "tool_calls": 0, "call_count": 1, "retry_count": 0})

    def test_self_declared_provider_flag_is_not_promoted(self):
        self.assertEqual(classify_measurement({"provider_reported": True, "measurement_source": "OFFLINE_IMPORT"})["grade"], "UNKNOWN")
        actual = classify_measurement({"provider_reported": True, "measurement_source": "PROVIDER_RESPONSE", "provider_response_id": "resp_123"})
        self.assertEqual(actual["grade"], "PROVIDER_REPORTED_USAGE")
        self.assertFalse(actual["provider_authenticated"])

    def test_request_envelopes_have_output_and_reasoning_controls(self):
        context = {"schema": "costdoctor.context-capsule.v1", "selected_context": [], "capsule_fingerprint": "a" * 64}
        openai = build_llm_request("openai", "registry-model", context, max_output_tokens=64, reasoning_effort="low", cache_key="cache")
        self.assertEqual(openai["request"]["max_output_tokens"], 64)
        self.assertEqual(openai["request"]["reasoning"], {"effort": "low"})
        self.assertFalse(openai["controls"]["network_executed"])
        self.assertEqual(build_llm_request("ollama", "registry-local", context, max_output_tokens=32)["request"]["num_predict"], 32)

    def _capsules(self):
        task_payload = {"task_id": "agent", "objective": "edit", "acceptance": ["tests"], "allowed_scope": ["universal"], "forbidden_scope": ["network"], "target_files": ["universal/README.md"], "output_contract": "patch"}
        state_payload = {"completed": [], "pending": ["edit"], "current_authority": "user", "current_version": "1", "blockers": [], "next_action": "test"}
        context = optimize_context({**task_payload, "required_fact_ids": ["goal"]}, state_payload, [{"id": "goal", "fact_id": "goal", "value": "safe edit", "required": True, "priority": 1}], 200)
        evidence = build_capsule("evidence", {"run_id": "r", "workload_id": "w", "metrics": {}, "quality": {}, "errors": [], "hashes": {}, "pointers": [], "verifier_result": {}})
        delta = build_capsule("delta", {"changed_facts": [], "changed_files": [], "changed_decisions": [], "invalidated_evidence": [], "new_requirements": []})
        return build_capsule("task", task_payload), build_capsule("state", state_payload), context, evidence, delta

    def test_coding_agent_packet_is_profile_driven_and_selective(self):
        registry = CodingAgentRegistry(ROOT / "universal" / "registry" / "agents")
        profile = registry.resolve("codex")
        repo_map = build_repo_map([{"path": "universal/README.md", "size": 20, "role": "docs", "changed": False, "digest": "b" * 64}])
        packet = build_coding_agent_packet(profile, *self._capsules(), repo_map)
        self.assertEqual(packet["selective_reads"], ["universal/README.md"])
        self.assertFalse(packet["raw_repo_embedded"])
        self.assertEqual(collect_coding_agent_usage(profile, {"usage": {"input_tokens": 10, "output_tokens": 2}})["measurement"]["grade"], "AVAILABLE_TOOL_USAGE")
        self.assertEqual(collect_coding_agent_usage(profile, {})["measurement"]["grade"], "UNKNOWN")

    def test_router_prefers_deterministic_then_requires_quality_for_escalation(self):
        rows = [
            {"id": "rule", "route_class": "deterministic", "capability_match": True, "quality": 1.0, "price_status": "KNOWN", "measurement_grade": "BYTE_PROXY", "cost_per_success_usd": "0"},
            {"id": "local", "route_class": "local", "capability_match": True, "quality": 1.0, "price_status": "KNOWN", "measurement_grade": "AVAILABLE_TOOL_USAGE", "cost_per_success_usd": "0"},
            {"id": "high", "route_class": "high", "capability_match": True, "quality": None, "price_status": "KNOWN", "measurement_grade": "PROVIDER_REPORTED_USAGE", "cost_per_success_usd": "0.1"},
        ]
        result = choose_execution_route(rows, 1.0)
        self.assertEqual(result["recommended"]["id"], "rule")
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
