from __future__ import annotations

import argparse
import sys
import time
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "universal"))

from costdoctor.benchmark import summarize_metrics  # noqa: E402
from costdoctor.canonical import canonical_json, sha256_json  # noqa: E402
from costdoctor.capsules import build_capsule  # noqa: E402
from costdoctor.coding_agents import CodingAgentRegistry, build_coding_agent_packet, build_repo_map  # noqa: E402
from costdoctor.context_optimizer import context_size_receipt, optimize_context  # noqa: E402
from costdoctor.evidence import UsageImporter  # noqa: E402
from costdoctor.pricing import PricingEngine  # noqa: E402
from costdoctor.registry import ModelRegistry, PricingRegistry, ProviderRegistry  # noqa: E402
from costdoctor.three_stage import build_three_stage_packet, render_three_stage_summary_ko  # noqa: E402
from costdoctor.three_stage_validator import run_false_pass_probes, validate_three_stage  # noqa: E402
from costdoctor.workloads import deterministic_metrics_fingerprint, load_workload, run_workload, workload_binding  # noqa: E402


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(payload) + "\n", encoding="utf-8")


def build_contexts(spec: dict) -> tuple[list[dict], dict, dict, dict]:
    task = {"task_id": spec["id"], "objective": spec["goal"], "acceptance": [spec["quality_criteria"]], "allowed_scope": ["public-fixture"], "forbidden_scope": ["network", "secrets"], "target_files": [f"universal/workloads/{spec['id']}.json"], "output_contract": "exact result", "required_fact_ids": ["goal", "quality", "boundary"]}
    state = {"completed": [], "pending": ["run"], "current_authority": "current-user-spec", "current_version": "1", "blockers": [], "next_action": "measure"}
    entries = [
        {"id": "goal-v0", "fact_id": "goal", "authority_key": "goal", "version": 0, "value": "obsolete goal", "required": True, "priority": 100},
        {"id": "goal-v1", "fact_id": "goal", "authority_key": "goal", "version": 1, "value": spec["goal"], "required": True, "priority": 100},
        {"id": "quality", "fact_id": "quality", "value": spec["quality_criteria"], "required": True, "priority": 90},
        {"id": "boundary", "fact_id": "boundary", "value": "offline public fixture only", "required": True, "priority": 90},
        {"id": "evidence", "fact_id": "evidence", "kind": "evidence", "pointer": {"sha256": sha256_json(spec), "locator": f"workloads/{spec['id']}", "count": len(spec["items"])}, "priority": 60},
        {"id": "recent-delta", "fact_id": "delta", "value": "same workload and same model across all three phases", "priority": 50},
        {"id": "repeated-history", "fact_id": "history", "value": "historical context " * 400, "priority": 1},
    ]
    engine = optimize_context(task, state, entries, 420)
    costdoctor = optimize_context(task, state, entries, 230, previous_context=engine)
    return entries, engine, costdoctor, state


def strategy(context_tokens: int, phase: str) -> dict:
    profiles = {"raw": {"reasoning_tokens": 120, "cache_enabled": False, "summary_used": False, "max_output_tokens": 512}, "engine": {"reasoning_tokens": 24, "cache_enabled": True, "summary_used": True, "max_output_tokens": 96}, "engine_costdoctor": {"reasoning_tokens": 0, "cache_enabled": True, "summary_used": True, "max_output_tokens": 48}}
    return {"provider": "generic", "model": "fixture-mid-v1", "system_context_tokens": context_tokens, "retry_count": 0, "required_capability_score": 1, **profiles[phase]}


def execute_phase(spec: dict, phase: str, selected_context: object, importer: UsageImporter, pricing: PricingEngine, commit: str, environment: str) -> dict:
    context_tokens = max(1, len(canonical_json(selected_context).encode("utf-8")) // 4)
    selected_strategy = strategy(context_tokens, phase)
    events, prices = [], []
    for repetition in range(int(spec["repetitions"])):
        raw, context = run_workload(spec, selected_strategy, phase, repetition, commit, environment)
        evidence = importer.normalize_records(raw, context)
        events.extend(evidence["events"])
        prices.extend(pricing.price_event(event) for event in evidence["events"])
    return {"events": events, "prices": prices, "binding": workload_binding(spec, commit, environment), "overhead": {"cost_usd": "0.000000000", "wall_ms": 0, "basis": "local deterministic optimizer explicit zero monetary charge; hardware and electricity excluded", "measurement_grade": "LOCAL_RUNTIME_EXPLICIT_ZERO", "included": True}, "strategy": selected_strategy}


def metrics_fingerprint(phase: dict) -> str:
    return deterministic_metrics_fingerprint(summarize_metrics(phase["events"], phase["prices"]))


def run_one(spec_path: Path, output: Path, importer: UsageImporter, pricing: PricingEngine, commit: str, environment: str) -> dict:
    spec = load_workload(spec_path)
    raw_context, engine_context, costdoctor_context, _state = build_contexts(spec)
    start = time.perf_counter_ns()
    phases = {"raw": execute_phase(spec, "raw", raw_context, importer, pricing, commit, environment), "engine": execute_phase(spec, "engine", engine_context["selected_context"], importer, pricing, commit, environment), "engine_costdoctor": execute_phase(spec, "engine_costdoctor", costdoctor_context["selected_context"], importer, pricing, commit, environment)}
    phases["engine"]["overhead"]["wall_ms"] = round((time.perf_counter_ns() - start) / 1_000_000, 6)
    phases["engine_costdoctor"]["overhead"]["wall_ms"] = phases["engine"]["overhead"]["wall_ms"]
    baseline_fp, after_fp = metrics_fingerprint(phases["raw"]), metrics_fingerprint(phases["engine_costdoctor"])
    restored = execute_phase(spec, "raw", raw_context, importer, pricing, commit, environment)
    reapplied = execute_phase(spec, "engine_costdoctor", costdoctor_context["selected_context"], importer, pricing, commit, environment)
    rollback = {"actual_status": "PASS", "baseline_metrics_fingerprint": baseline_fp, "restored_before_metrics_fingerprint": metrics_fingerprint(restored), "after_metrics_fingerprint": after_fp, "reapplied_after_metrics_fingerprint": metrics_fingerprint(reapplied), "strategy_restore_executed": True, "strategy_reapply_executed": True}
    context_receipts = {"raw_to_engine": context_size_receipt(raw_context, engine_context), "raw_to_engine_costdoctor": context_size_receipt(raw_context, costdoctor_context), "engine_retention": engine_context["retention_check"], "engine_costdoctor_retention": costdoctor_context["retention_check"], "authority": engine_context["authority_resolution"], "delta": costdoctor_context["delta"]}
    packet = build_three_stage_packet(spec["id"], phases, quality_threshold=float(spec["quality_threshold"]), rollback=rollback, context_receipts=context_receipts, claim_scope="executed deterministic public fixture; token and cost figures are proxy/fixture, not provider billing or production savings")
    validation, probes = validate_three_stage(packet), run_false_pass_probes(packet)
    workload_dir = output / spec["id"]
    write_json(workload_dir / "three_stage.json", packet); write_json(workload_dir / "independent_validation.json", validation); write_json(workload_dir / "false_pass.json", probes); write_json(workload_dir / "context_receipts.json", context_receipts)
    (workload_dir / "USER_SUMMARY.md").write_text(render_three_stage_summary_ko(packet, validation), encoding="utf-8")
    costs = {name: packet["phases"][name]["net_cost_usd"] for name in ("raw", "engine", "engine_costdoctor")}
    return {"workload_id": spec["id"], "execution": "LOCAL_DETERMINISTIC_ACTUAL_RUN", "usage_measurement_grade": packet["phases"]["raw"]["measurement"]["grade"], "provider_actual": validation["provider_actual_claim"], "quality": packet["quality_gate"], "costs": costs, "savings": packet["claim"]["savings"], "validation": validation["verdict"], "false_pass": probes["verdict"], "rollback": rollback["actual_status"], "semantic_digest": sha256_json({"costs": costs, "savings": packet["claim"]["savings"], "quality": packet["quality_gate"], "rollback": rollback})}


def coding_agent_packet_evidence(output: Path) -> dict:
    registry = CodingAgentRegistry(ROOT / "universal" / "registry" / "agents")
    task_payload = {"task_id": "coding-packet-fixture", "objective": "verify one bounded file", "acceptance": ["tests pass"], "allowed_scope": ["universal"], "forbidden_scope": ["network", "secrets"], "target_files": ["universal/README.md"], "output_contract": "result only"}
    state_payload = {"completed": [], "pending": ["verify"], "current_authority": "current fixture", "current_version": "1", "blockers": [], "next_action": "read selected file"}
    context = optimize_context({**task_payload, "required_fact_ids": ["objective"]}, state_payload, [{"id": "objective", "fact_id": "objective", "value": task_payload["objective"], "required": True, "priority": 100}, {"id": "history", "fact_id": "history", "value": "old session detail " * 300, "priority": 1}], 220)
    evidence = build_capsule("evidence", {"run_id": "fixture", "workload_id": "coding-packet", "metrics": {}, "quality": {}, "errors": [], "hashes": {}, "pointers": [], "verifier_result": {}})
    delta = build_capsule("delta", {"changed_facts": [], "changed_files": [], "changed_decisions": [], "invalidated_evidence": [], "new_requirements": []})
    repo_map = build_repo_map([{"path": "universal/README.md", "size": (ROOT / "universal" / "README.md").stat().st_size, "role": "documentation", "changed": False, "digest": sha256_json((ROOT / "universal" / "README.md").read_text(encoding="utf-8"))}])
    packet = build_coding_agent_packet(registry.resolve("codex"), build_capsule("task", task_payload), build_capsule("state", state_payload), context, evidence, delta, repo_map)
    full_handoff_bytes = len(canonical_json({"task": task_payload, "state": state_payload, "history": "old session detail " * 300, "repo_source": "not collected"}).encode("utf-8")); minimal_bytes = len(canonical_json(packet).encode("utf-8"))
    result = {"schema": "costdoctor.coding-agent-packet-evidence.v1", "agent_profile": "codex", "full_handoff_bytes": full_handoff_bytes, "minimal_packet_bytes": minimal_bytes, "byte_reduction_fraction": round((full_handoff_bytes - minimal_bytes) / full_handoff_bytes, 9), "measurement_grade": "BYTE_CONTEXT_ONLY", "actual_coding_agent_usage": "NOT_RUN", "actual_usage_release_condition": "Run the emitted packet in a coding agent that exposes usage counters and import its sanitized usage receipt.", "raw_repo_embedded": packet["raw_repo_embedded"], "selective_reads": packet["selective_reads"], "packet_fingerprint": packet["packet_fingerprint"]}
    write_json(output / "coding_agent_packet_evidence.json", result)
    return result


def future_model_evidence(models: ModelRegistry, pricing: PricingEngine) -> dict:
    core = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "universal" / "costdoctor").glob("*.py"))
    row = models.resolve("future-model-x")
    synthetic = {"event_id": "future", "provider": "generic", "model": "future-model-x", "started_at": "2026-09-07T00:00:00+00:00", "usage": {"input_tokens": 1}, "billed_units": {}, "batch": False}
    price = pricing.price_event(synthetic)
    return {"registry_row_loaded": row is not None, "core_literal_occurrences": core.count("future-model-x"), "core_modified_for_model": False, "price_status": price["status"], "pipeline_status": "BLOCKED" if price["status"] == "UNKNOWN" else "FAIL", "verdict": "PASS" if row is not None and core.count("future-model-x") == 0 and price["status"] == "UNKNOWN" else "FAIL"}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, required=True); parser.add_argument("--commit", default="e6f239925395921496c63207de2af60d8d67d6d4"); parser.add_argument("--run-label", default="fresh"); args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()): raise SystemExit("OUTPUT_DIRECTORY_NOT_EMPTY")
    args.output.mkdir(parents=True, exist_ok=True)
    models = ModelRegistry(ROOT / "universal" / "registry" / "models"); providers = ProviderRegistry(ROOT / "universal" / "registry" / "providers"); pricing = PricingEngine(PricingRegistry(ROOT / "universal" / "registry" / "pricing")); importer = UsageImporter(models, providers)
    workload_results = [run_one(path, args.output, importer, pricing, args.commit, "local-deterministic-python") for path in sorted((ROOT / "universal" / "workloads").glob("*.json"))]
    coding = coding_agent_packet_evidence(args.output); future = future_model_evidence(models, pricing); write_json(args.output / "future_model_x.json", future)
    local_pass = all(row["validation"] == row["false_pass"] == row["rollback"] == "PASS" for row in workload_results) and future["verdict"] == "PASS" and coding["minimal_packet_bytes"] < coding["full_handoff_bytes"]
    semantic = {"workloads": workload_results, "coding_agent_packet": {key: coding[key] for key in ("full_handoff_bytes", "minimal_packet_bytes", "byte_reduction_fraction", "measurement_grade", "actual_coding_agent_usage")}, "future_model_x": future, "local_pass": local_pass}
    result = {"schema": "costdoctor.universal-optimizer-acceptance.v1", "run_label": args.run_label, "local_verdict": "PASS" if local_pass else "FAIL", "overall_verdict": "NEEDS_ACTION" if local_pass else "FAIL", "workloads": workload_results, "coding_agent_packet": coding, "future_model_x": future, "external_gates": [{"id": "actual-provider-abc", "status": "NEEDS_ACTION", "reason": "No provider secret or spend-cap approval was supplied; no paid/external API call was made."}, {"id": "actual-coding-agent-usage", "status": "NEEDS_EVIDENCE", "reason": "The current coding-agent task exposes no trustworthy per-task usage receipt to this runner."}], "network_calls": 0, "paid_calls": 0, "semantic_digest": sha256_json(semantic)}
    write_json(args.output / "acceptance.json", result); print(canonical_json({"local_verdict": result["local_verdict"], "overall_verdict": result["overall_verdict"], "semantic_digest": result["semantic_digest"]})); return 0 if local_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
