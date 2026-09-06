from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


REPOSITORY = Path(__file__).resolve().parents[2]
UNIVERSAL = REPOSITORY / "universal"
sys.path.insert(0, str(UNIVERSAL))

from costdoctor.benchmark import build_benchmark_packet, summarize_metrics  # noqa: E402
from costdoctor.canonical import canonical_json, sha256_bytes, sha256_json, utc_now  # noqa: E402
from costdoctor.detectors import detect_waste  # noqa: E402
from costdoctor.evidence import UsageImporter, verify_receipt_chain  # noqa: E402
from costdoctor.github_guard import inspect_github_boundaries  # noqa: E402
from costdoctor.pricing import PricingEngine  # noqa: E402
from costdoctor.registry import ModelRegistry, PricingRegistry, ProviderRegistry  # noqa: E402
from costdoctor.report import render_report  # noqa: E402
from costdoctor.report_validator import validate_user_report  # noqa: E402
from costdoctor.routing import advise_routing  # noqa: E402
from costdoctor.self_dogfood import artifact_size, environment_fingerprint, measure_self_dogfood  # noqa: E402
from costdoctor.user_report import (  # noqa: E402
    build_user_report,
    render_user_report_html,
    render_user_summary_markdown,
)
from costdoctor.validator import validate_packet  # noqa: E402
from costdoctor.verified_fix import prepare_verified_fix_plan  # noqa: E402
from costdoctor.workloads import (  # noqa: E402
    deterministic_metrics_fingerprint,
    load_workload,
    run_workload,
    workload_binding,
)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def repository_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def core_snapshot() -> dict[str, Any]:
    entries = []
    for path in sorted((UNIVERSAL / "costdoctor").glob("*.py")):
        raw = path.read_bytes()
        entries.append(
            {
                "path": path.relative_to(REPOSITORY).as_posix(),
                "sha256": sha256_bytes(raw),
                "future_model_literal_present": b"future-model-x" in raw,
            }
        )
    return {
        "files": entries,
        "aggregate_sha256": sha256_json(entries),
        "future_model_literal_count": sum(1 for item in entries if item["future_model_literal_present"]),
    }


def execute_phase(
    spec: dict[str, Any],
    strategy: dict[str, Any],
    phase: str,
    commit: str,
    env_fingerprint: str,
    importer: UsageImporter,
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    run_evidence: list[dict[str, Any]] = []
    for repetition in range(int(spec["repetitions"])):
        raw, context = run_workload(spec, strategy, phase, repetition, commit, env_fingerprint)
        evidence = importer.normalize_records(raw, context)
        if not verify_receipt_chain(evidence):
            raise RuntimeError("RECEIPT_CHAIN_FAILED")
        events.extend(evidence["events"])
        run_evidence.append(evidence)
    return {
        "phase": phase,
        "strategy": deepcopy(strategy),
        "events": events,
        "run_evidence": run_evidence,
        "receipt_chains_verified": all(verify_receipt_chain(item) for item in run_evidence),
    }


def price_events(events: list[dict[str, Any]], engine: PricingEngine) -> list[dict[str, Any]]:
    return [engine.price_event(event) for event in events]


def stable_metrics(events: list[dict[str, Any]], prices: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    metrics = summarize_metrics(events, prices)
    return metrics, deterministic_metrics_fingerprint(metrics)


def write_user_report_bundle(
    target: Path,
    packet: dict[str, Any],
    validation: dict[str, Any],
    application_state: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    report = build_user_report(packet, validation, application_state)
    easy_html = render_user_report_html(report)
    print_html = render_user_report_html(report, printable=True)
    regenerated = build_user_report(packet, validation, application_state)
    regenerated_easy = render_user_report_html(regenerated)
    regenerated_print = render_user_report_html(regenerated, printable=True)
    report_validation = validate_user_report(
        packet,
        validation,
        report,
        easy_html,
        print_html,
        expected_application_state=application_state,
        regenerated_report=regenerated,
        regenerated_easy_html=regenerated_easy,
        regenerated_print_html=regenerated_print,
    )
    write_json(target / "user_report.json", report)
    write_json(target / "user_report_independent_validation.json", report_validation)
    (target / "EASY_REPORT.html").write_text(easy_html, encoding="utf-8")
    (target / "PRINT_REPORT.html").write_text(print_html, encoding="utf-8")
    (target / "USER_SUMMARY.md").write_text(render_user_summary_markdown(report), encoding="utf-8")
    return report, report_validation


def run_benchmark(
    spec_path: Path,
    output: Path,
    commit: str,
    env_fingerprint: str,
    models: ModelRegistry,
    providers: ProviderRegistry,
    pricing: PricingEngine,
) -> dict[str, Any]:
    spec = load_workload(spec_path)
    importer = UsageImporter(models, providers)
    before = execute_phase(spec, spec["before"], "before", commit, env_fingerprint, importer)
    improved = execute_phase(spec, spec["after"], "after", commit, env_fingerprint, importer)
    rollback_run = execute_phase(spec, spec["before"], "rollback-before", commit, env_fingerprint, importer)
    reapplied = execute_phase(spec, spec["after"], "reapply-after", commit, env_fingerprint, importer)

    before_prices = price_events(before["events"], pricing)
    improved_prices = price_events(improved["events"], pricing)
    rollback_prices = price_events(rollback_run["events"], pricing)
    reapplied_prices = price_events(reapplied["events"], pricing)

    before_metrics, before_fingerprint = stable_metrics(before["events"], before_prices)
    improved_metrics, improved_fingerprint = stable_metrics(improved["events"], improved_prices)
    rollback_metrics, rollback_fingerprint = stable_metrics(rollback_run["events"], rollback_prices)
    reapplied_metrics, reapplied_fingerprint = stable_metrics(reapplied["events"], reapplied_prices)
    rollback = {
        "actual_status": "PASS"
        if before_fingerprint == rollback_fingerprint and improved_fingerprint == reapplied_fingerprint
        else "FAIL",
        "method": "restore_before_strategy_then_execute_actual_workload_then_reapply_after_strategy",
        "baseline_metrics_fingerprint": before_fingerprint,
        "restored_before_metrics_fingerprint": rollback_fingerprint,
        "after_metrics_fingerprint": reapplied_fingerprint,
        "reapplied_after_metrics_fingerprint": improved_fingerprint,
        "baseline_metrics": before_metrics,
        "rollback_metrics": rollback_metrics,
        "initial_after_metrics": improved_metrics,
        "reapplied_after_metrics": reapplied_metrics,
    }

    binding = workload_binding(spec, commit, env_fingerprint)
    if spec.get("routing_requirements"):
        routing = advise_routing(spec["routing_requirements"], models, pricing, spec.get("observed_candidates"))
    else:
        routing = {
            "schema": "costdoctor.routing-advice.v1",
            "verdict": "NOT_APPLICABLE",
            "reason": "WORKLOAD_OPTIMIZES_CONTEXT_AND_RETRY_WITHOUT_MODEL_ROUTE_CHANGE",
            "applied": False,
        }
    detectors = detect_waste(before["events"], models)
    packet = build_benchmark_packet(
        workload_id=spec["id"],
        before_events=before["events"],
        after_events=reapplied["events"],
        before_prices=before_prices,
        after_prices=reapplied_prices,
        before_binding=binding,
        after_binding=deepcopy(binding),
        threshold=float(spec["quality_threshold"]),
        rollback=rollback,
        detectors=detectors,
        routing=routing,
        claim_scope="DETERMINISTIC_PUBLIC_FIXTURE_ONLY_NOT_PRODUCTION_SAVINGS",
    )
    validation = validate_packet(packet)
    verified_claim = {
        "schema": "costdoctor.verified-savings-claim.v1",
        "status": "VERIFIED" if validation["verdict"] == "PASS" else "BLOCKED",
        "scope": packet["claim_scope"],
        "workload_id": spec["id"],
        "producer_digest": packet["producer_digest"],
        "validator_digest": validation["validator_digest"],
        "verified_savings_usd": validation["verified_savings_usd"],
        "claim_level": validation["claim_level"],
        "production_claim_allowed": False,
    }

    target = output / "workloads" / spec["id"]
    write_json(target / "before_usage_evidence.json", before)
    write_json(target / "initial_after_usage_evidence.json", improved)
    write_json(target / "rollback_usage_evidence.json", rollback_run)
    write_json(target / "reapplied_after_usage_evidence.json", reapplied)
    write_json(target / "benchmark_packet.json", packet)
    write_json(target / "independent_validation.json", validation)
    write_json(target / "verified_claim.json", verified_claim)
    (target / "report.ko.md").write_text(render_report(packet, validation, "ko"), encoding="utf-8")
    (target / "report.en.md").write_text(render_report(packet, validation, "en"), encoding="utf-8")
    user_report, report_validation = write_user_report_bundle(
        target, packet, validation, "APPLIED_AND_VERIFIED"
    )
    return {
        "workload_id": spec["id"],
        "actual_phases": ["before", "after", "rollback-before", "reapply-after"],
        "actual_runs": int(spec["repetitions"]) * 4,
        "event_count": sum(len(item["events"]) for item in (before, improved, rollback_run, reapplied)),
        "receipt_chains_verified": all(
            item["receipt_chains_verified"] for item in (before, improved, rollback_run, reapplied)
        ),
        "quality_verdict": packet["quality"]["verdict"],
        "rollback_verdict": rollback["actual_status"],
        "independent_validation": validation["verdict"],
        "user_report_independent_validation": report_validation["verdict"],
        "user_report_facts_digest": sha256_json(user_report["facts"]),
        "user_report_deterministic": report_validation["deterministic_regeneration"] == "PASS",
        "verified_savings_usd": validation["verified_savings_usd"],
        "routing_verdict": routing["verdict"],
        "detector_count": len(detectors),
        "before_metrics_fingerprint": before_fingerprint,
        "after_metrics_fingerprint": reapplied_fingerprint,
    }


def future_model_test(
    output: Path,
    commit: str,
    env_fingerprint: str,
    models: ModelRegistry,
    providers: ProviderRegistry,
    base_pricing_registry: PricingRegistry,
    core_before: dict[str, Any],
) -> dict[str, Any]:
    spec = load_workload(UNIVERSAL / "workloads" / "repeated-context.v1.json")
    future_strategy = deepcopy(spec["after"])
    future_strategy["model"] = "future-x-preview"
    importer = UsageImporter(models, providers)
    before = execute_phase(spec, future_strategy, "future-before", commit, env_fingerprint, importer)
    after = execute_phase(spec, future_strategy, "future-after", commit, env_fingerprint, importer)
    rollback_run = execute_phase(spec, future_strategy, "future-rollback", commit, env_fingerprint, importer)
    reapplied = execute_phase(spec, future_strategy, "future-reapply", commit, env_fingerprint, importer)
    base_engine = PricingEngine(base_pricing_registry)
    before_prices = price_events(before["events"], base_engine)
    after_prices = price_events(after["events"], base_engine)
    before_metrics, before_fingerprint = stable_metrics(before["events"], before_prices)
    after_metrics, after_fingerprint = stable_metrics(after["events"], after_prices)
    rollback_metrics, rollback_fingerprint = stable_metrics(
        rollback_run["events"], price_events(rollback_run["events"], base_engine)
    )
    reapply_metrics, reapply_fingerprint = stable_metrics(
        reapplied["events"], price_events(reapplied["events"], base_engine)
    )
    rollback = {
        "actual_status": "PASS"
        if rollback_fingerprint == before_fingerprint and reapply_fingerprint == after_fingerprint
        else "FAIL",
        "baseline_metrics_fingerprint": before_fingerprint,
        "restored_before_metrics_fingerprint": rollback_fingerprint,
        "after_metrics_fingerprint": after_fingerprint,
        "reapplied_after_metrics_fingerprint": reapply_fingerprint,
        "baseline_metrics": before_metrics,
        "rollback_metrics": rollback_metrics,
        "reapplied_after_metrics": reapply_metrics,
    }
    binding = workload_binding(spec, commit, env_fingerprint)
    packet = build_benchmark_packet(
        workload_id="future-model-x-compatibility",
        before_events=before["events"],
        after_events=after["events"],
        before_prices=before_prices,
        after_prices=after_prices,
        before_binding=binding,
        after_binding=deepcopy(binding),
        threshold=float(spec["quality_threshold"]),
        rollback=rollback,
        detectors=detect_waste(before["events"], models),
        routing={"verdict": "BLOCKED", "reason": "CAPABILITY_AND_PRICE_UNKNOWN", "applied": False},
        claim_scope="FUTURE_MODEL_COMPATIBILITY_FIXTURE_ONLY",
    )
    validation = validate_packet(packet)

    overlay_dir = output / "registry_overlays" / "future-model-price"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(UNIVERSAL / "registry" / "pricing" / "fixture-prices.v1.json", overlay_dir / "fixture-prices.v1.json")
    overlay = {
        "schema": "costdoctor.pricing-registry.v1",
        "rows": [
            {
                "provider": "generic",
                "model": "future-model-x",
                "price_version": "future-fixture-user-defined-v1",
                "effective_from": "2026-09-06T00:00:00+00:00",
                "effective_to": None,
                "status": "user_defined",
                "source": "Acceptance fixture added as Registry data only",
                "verified_at": utc_now(),
                "unit_rates_usd": {
                    "input_tokens": 1,
                    "output_tokens": 2,
                    "cached_input_tokens": 0.1,
                    "cache_write_tokens": 0.5,
                    "reasoning_tokens": 1,
                    "tool_calls": 0,
                },
                "custom_unit_rates_usd": {},
                "batch_discount_fraction": 0,
                "request_minimum_usd": 0,
                "rounding_decimals": 9,
            }
        ],
    }
    write_json(overlay_dir / "future-model-price.v1.json", overlay)
    future_engine = PricingEngine(PricingRegistry(overlay_dir))
    recalculated = future_engine.price_event(after["events"][0])
    core_after = core_snapshot()
    result = {
        "schema": "costdoctor.future-model-compatibility.v1",
        "model_resolved_from_registry": models.resolve("future-x-preview")["canonical_id"] == "future-model-x",
        "core_literal_count": core_after["future_model_literal_count"],
        "core_before_sha256": core_before["aggregate_sha256"],
        "core_after_sha256": core_after["aggregate_sha256"],
        "core_code_changes": 0 if core_before["aggregate_sha256"] == core_after["aggregate_sha256"] else 1,
        "usage_ingest": "PASS" if before["events"] else "FAIL",
        "unknown_price_status": before_prices[0]["status"],
        "unknown_claim_status": packet["claim"]["status"],
        "unknown_independent_validation": validation["verdict"],
        "unknown_verified_savings_usd": validation["verified_savings_usd"],
        "data_only_price_recalculation_status": recalculated["status"],
        "data_only_price_recalculation_cost_usd": recalculated["cost_usd"],
        "report_generation": "PENDING",
        "rollback_actual": rollback["actual_status"],
    }
    future_target = output / "future_model"
    user_report, report_validation = write_user_report_bundle(
        future_target, packet, validation, "NOT_APPLICABLE"
    )
    result["report_generation"] = "PASS" if user_report else "FAIL"
    result["user_report_independent_validation"] = report_validation["verdict"]
    result["user_report_facts_digest"] = sha256_json(user_report["facts"])
    result["verdict"] = "PASS" if all(
        [
            result["model_resolved_from_registry"],
            result["core_literal_count"] == 0,
            result["core_code_changes"] == 0,
            result["usage_ingest"] == "PASS",
            result["unknown_price_status"] == "UNKNOWN",
            result["unknown_claim_status"] == "UNKNOWN",
            result["unknown_independent_validation"] == "BLOCKED",
            result["unknown_verified_savings_usd"] is None,
            result["data_only_price_recalculation_status"] == "MEASURED_PRICE_APPLIED",
            result["report_generation"] == "PASS",
            result["user_report_independent_validation"] == "PASS",
            result["rollback_actual"] == "PASS",
        ]
    ) else "FAIL"
    write_json(output / "future_model" / "benchmark_packet_unknown.json", packet)
    write_json(output / "future_model" / "independent_validation_unknown.json", validation)
    write_json(output / "future_model" / "compatibility_result.json", result)
    (output / "future_model" / "report.ko.md").write_text(render_report(packet, validation, "ko"), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CostDoctor Universal R1 actual acceptance workloads offline.")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output == REPOSITORY or REPOSITORY in output.parents:
        raise SystemExit("OUTPUT_MUST_BE_OUTSIDE_REPOSITORY")
    output.mkdir(parents=True, exist_ok=False)

    commit = repository_commit()
    env_fingerprint = environment_fingerprint()
    models = ModelRegistry(UNIVERSAL / "registry" / "models")
    providers = ProviderRegistry(UNIVERSAL / "registry" / "providers")
    pricing_registry = PricingRegistry(UNIVERSAL / "registry" / "pricing")
    pricing = PricingEngine(pricing_registry)
    core_before = core_snapshot()
    dogfood: dict[str, Any] = {}
    with measure_self_dogfood(dogfood):
        workloads = [
            run_benchmark(
                UNIVERSAL / "workloads" / "repeated-context.v1.json",
                output,
                commit,
                env_fingerprint,
                models,
                providers,
                pricing,
            ),
            run_benchmark(
                UNIVERSAL / "workloads" / "routing.v1.json",
                output,
                commit,
                env_fingerprint,
                models,
                providers,
                pricing,
            ),
        ]
        future = future_model_test(
            output, commit, env_fingerprint, models, providers, pricing_registry, core_before
        )
        github = inspect_github_boundaries(REPOSITORY)
        verified_fix = prepare_verified_fix_plan(sha256_json(workloads), sha256_json({"rollback": workloads}))

    dogfood["artifact_size_bytes"] = artifact_size(output)
    dogfood["verdict"] = "PASS" if all(
        dogfood[key] == 0 for key in ("network_calls", "model_calls", "tokens", "paid_calls")
    ) else "FAIL"
    write_json(output / "self_dogfood.json", dogfood)
    write_json(output / "github_guard.json", github)
    write_json(output / "verified_fix_guard.json", verified_fix)
    write_json(
        output / "registry_snapshot.json",
        {
            "models": models.snapshot,
            "providers": providers.snapshot,
            "pricing": pricing_registry.snapshot,
        },
    )
    checks = {
        "two_actual_workloads": len(workloads) >= 2,
        "all_workloads_independently_validated": all(item["independent_validation"] == "PASS" for item in workloads),
        "all_user_reports_independently_validated": all(
            item["user_report_independent_validation"] == "PASS" for item in workloads
        ),
        "all_user_reports_deterministic": all(item["user_report_deterministic"] for item in workloads),
        "all_quality_guards_pass": all(item["quality_verdict"] == "PASS" for item in workloads),
        "all_rollbacks_actual_pass": all(item["rollback_verdict"] == "PASS" for item in workloads),
        "all_receipt_chains_pass": all(item["receipt_chains_verified"] for item in workloads),
        "future_model_data_only_pass": future["verdict"] == "PASS",
        "github_boundaries_pass": github["verdict"] == "PASS",
        "verified_fix_write_disabled": not verified_fix["repository_write"],
        "self_dogfood_pass": dogfood["verdict"] == "PASS",
        "offline_only": dogfood["network_calls"] == 0 and dogfood["paid_calls"] == 0,
    }
    summary = {
        "schema": "costdoctor.universal-acceptance-run.v1",
        "generated_at": utc_now(),
        "repository_commit": commit,
        "environment_fingerprint": env_fingerprint,
        "execution": "ACTUAL_LOCAL_DETERMINISTIC_FRESH",
        "workloads": workloads,
        "future_model": future,
        "checks": checks,
        "verdict": "PASS" if all(checks.values()) else "FAIL",
        "claim_boundary": "Fixture savings are verified only for these executed fixtures; production savings remain unclaimed.",
    }
    summary["summary_digest"] = sha256_json(summary)
    write_json(output / "acceptance_summary.json", summary)
    print(canonical_json({"verdict": summary["verdict"], "output": str(output), "digest": summary["summary_digest"]}))
    return 0 if summary["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
