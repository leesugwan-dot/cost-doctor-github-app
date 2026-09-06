from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Any

from .registry import ModelRegistry


DETECTOR_IDS = (
    "duplicate_call",
    "identical_input_repeat",
    "repeated_prefix",
    "oversized_context",
    "full_history_reinjection",
    "duplicate_retrieval",
    "low_relevance_rag",
    "excessive_output_limit",
    "inefficient_chunk_overlap",
    "inefficient_chunk_size",
    "summary_missing",
    "excessive_retry",
    "same_error_retry",
    "retry_backoff_invalid",
    "full_reexecution_after_failure",
    "timeout_duplicate",
    "idempotency_missing",
    "cache_missing",
    "low_cache_hit_rate",
    "cache_ttl_mismatch",
    "cache_scope_unsafe",
    "cache_cost_exceeds_saving",
    "overqualified_model",
    "simple_task_expensive_model",
    "excessive_reasoning",
    "fallback_chain_excess",
    "model_switch_rework",
    "repeated_tool_loop",
    "planner_reviewer_duplication",
    "multi_agent_duplicate",
    "repeated_fetch",
    "large_tool_output_reinjection",
    "model_used_for_local_compute",
    "serial_parallelizable_calls",
    "batch_opportunity",
    "concurrency_retry_amplification",
    "queue_duplicate_execution",
    "model_occupied_while_waiting",
    "failure_cost_spike",
    "latency_spike",
    "tool_rework_cost",
)


def _finding(
    detector_id: str,
    category: str,
    evidence: dict[str, Any],
    recommendation: str,
    risk: str,
    rollback: str,
    confidence: str = "MEASURED",
) -> dict[str, Any]:
    return {
        "detector": detector_id,
        "category": category,
        "evidence": evidence,
        "confidence": confidence,
        "evidence_kind": "MEASURED_RUNTIME" if confidence == "MEASURED" else "STATIC_SIGNAL",
        "potential_savings": "REQUIRES_BENCHMARK",
        "verified_savings_usd": None,
        "recommendation": recommendation,
        "risk": risk,
        "rollback": rollback,
    }


def detect_waste(events: list[dict[str, Any]], models: ModelRegistry) -> list[dict[str, Any]]:
    if not events:
        return []
    findings: list[dict[str, Any]] = []
    count = len(events)
    inputs = Counter(event.get("input_fingerprint") for event in events if event.get("input_fingerprint"))
    contexts = Counter(event.get("context_fingerprint") for event in events if event.get("context_fingerprint"))
    duplicate_calls = sum(value - 1 for value in inputs.values() if value > 1)
    repeated_context = sum(value - 1 for value in contexts.values() if value > 1)
    retries = sum(int(event["usage"].get("retry_count", 0)) for event in events)
    failures = sum(1 for event in events if not event["success"])
    cache_hits = sum(1 for event in events if event.get("cache_hit"))
    tool_calls = sum(int(event["usage"].get("tool_calls", 0)) for event in events)
    latencies = [float(event["latency_ms"]) for event in events]

    if duplicate_calls:
        findings.append(_finding("duplicate_call", "calls_routing", {"duplicate_event_count": duplicate_calls}, "Deduplicate identical workload fingerprints before calling a model.", "Different user or authorization scopes must never share results.", "Disable deduplication and restore per-request execution."))
        findings.append(_finding("identical_input_repeat", "calls_routing", {"repeated_input_fingerprint_count": duplicate_calls}, "Reuse only scope-bound results for identical inputs or explain why a fresh call is required.", "Input fingerprints must include authorization and relevant configuration boundaries.", "Disable identical-input reuse."))
    if repeated_context:
        findings.append(_finding("repeated_prefix", "tokens_context", {"repeated_context_count": repeated_context}, "Bind and reuse a safe prefix cache or compact the repeated prefix.", "Cache scope or TTL mistakes can expose stale or cross-user context.", "Disable the prefix cache and restore full context injection."))
    if sum(int(event["usage"].get("input_tokens", 0)) for event in events) > count * 100:
        findings.append(_finding("oversized_context", "tokens_context", {"input_tokens": sum(int(event["usage"].get("input_tokens", 0)) for event in events)}, "Measure relevance and remove context that does not affect quality.", "Removing context can reduce answer quality.", "Restore the prior context assembly."))
    if any(event.get("metadata", {}).get("full_history_reinjected") for event in events):
        findings.append(_finding("full_history_reinjection", "tokens_context", {"affected_events": sum(1 for event in events if event.get("metadata", {}).get("full_history_reinjected"))}, "Use a bounded summary plus the minimum recent turns.", "Summaries can omit requirements.", "Restore the prior history window."))
    duplicate_retrieval = sum(int(event.get("metadata", {}).get("duplicate_retrieved_documents", 0)) for event in events)
    if duplicate_retrieval:
        findings.append(_finding("duplicate_retrieval", "tokens_context", {"duplicate_documents": duplicate_retrieval}, "Deduplicate retrieved document identities before context assembly.", "Document-version identity mistakes can remove distinct evidence.", "Restore the previous retrieval assembly."))
    low_relevance = [event for event in events if event.get("metadata", {}).get("retrieved_tokens", 0) and event.get("metadata", {}).get("relevant_tokens", 0) / event["metadata"]["retrieved_tokens"] < 0.5]
    if low_relevance:
        findings.append(_finding("low_relevance_rag", "tokens_context", {"affected_events": len(low_relevance)}, "Raise retrieval relevance or reduce duplicate documents.", "Stricter retrieval can miss supporting material.", "Restore the prior retriever settings."))
    excessive_output = [event for event in events if event.get("metadata", {}).get("max_output_tokens", 0) > max(32, event["usage"].get("output_tokens", 0) * 4)]
    if excessive_output:
        findings.append(_finding("excessive_output_limit", "tokens_context", {"affected_events": len(excessive_output)}, "Set an evidence-based output limit with a quality guard.", "Too-low limits can truncate answers.", "Restore the former output limit."))
    if any(event.get("metadata", {}).get("chunk_overlap_ratio", 0) > 0.5 for event in events):
        findings.append(_finding("inefficient_chunk_overlap", "tokens_context", {"affected_events": sum(1 for event in events if event.get("metadata", {}).get("chunk_overlap_ratio", 0) > 0.5)}, "Reduce measured duplicate chunk overlap.", "Lower overlap can split needed context.", "Restore the previous chunk policy."))
    if any(event.get("metadata", {}).get("chunk_tokens", 0) > event.get("metadata", {}).get("useful_chunk_tokens", float("inf")) * 2 for event in events):
        findings.append(_finding("inefficient_chunk_size", "tokens_context", {"affected_events": sum(1 for event in events if event.get("metadata", {}).get("chunk_tokens", 0) > event.get("metadata", {}).get("useful_chunk_tokens", float("inf")) * 2)}, "Benchmark smaller chunks against retrieval quality.", "Smaller chunks can remove necessary local context.", "Restore the previous chunk size."))
    if any(not event.get("metadata", {}).get("summary_used", True) and event.get("metadata", {}).get("conversation_turns", 0) > 12 for event in events):
        findings.append(_finding("summary_missing", "tokens_context", {"affected_events": sum(1 for event in events if not event.get("metadata", {}).get("summary_used", True))}, "Benchmark bounded summarization against the same quality assertions.", "Summary loss can cause rework.", "Disable summarization."))

    if retries:
        findings.append(_finding("excessive_retry", "retry_failure", {"retry_count": retries}, "Classify errors and retry only transient failures with a cap.", "Too few retries can reduce completion.", "Restore the previous retry policy."))
    error_counts = Counter(event.get("error_class") for event in events if event.get("error_class"))
    repeated_errors = sum(value - 1 for value in error_counts.values() if value > 1)
    if repeated_errors:
        findings.append(_finding("same_error_retry", "retry_failure", {"repeated_error_count": repeated_errors}, "Stop retrying deterministic errors and surface a bounded failure.", "Some errors may be misclassified as permanent.", "Restore retry classification."))
    if retries and any(event.get("metadata", {}).get("retry_backoff_ms", 0) <= 0 for event in events):
        findings.append(_finding("retry_backoff_invalid", "retry_failure", {"affected_events": sum(1 for event in events if event["usage"].get("retry_count", 0) and event.get("metadata", {}).get("retry_backoff_ms", 0) <= 0)}, "Use bounded exponential backoff only for transient failures.", "Long backoff can exceed user latency targets.", "Restore the prior retry timing."))
    if any(event.get("metadata", {}).get("full_reexecution") for event in events):
        findings.append(_finding("full_reexecution_after_failure", "retry_failure", {"affected_events": sum(1 for event in events if event.get("metadata", {}).get("full_reexecution"))}, "Resume from the last safe checkpoint.", "Checkpoint state can be stale.", "Return to full execution."))
    if any(event.get("metadata", {}).get("timeout_duplicate") for event in events):
        findings.append(_finding("timeout_duplicate", "retry_failure", {"affected_events": sum(1 for event in events if event.get("metadata", {}).get("timeout_duplicate"))}, "Bind timeouts to idempotency and completion receipts.", "Incorrect idempotency can suppress valid work.", "Disable the dedupe key."))
    if retries and any(not event.get("metadata", {}).get("idempotency_key") for event in events):
        findings.append(_finding("idempotency_missing", "retry_failure", {"events_without_key": sum(1 for event in events if not event.get("metadata", {}).get("idempotency_key"))}, "Add scope-bound idempotency keys before retries.", "Keys must include tenant and authorization scope.", "Remove the key and restore prior retry flow."))

    if any(event.get("metadata", {}).get("cache_eligible") and not event.get("cache_hit") for event in events):
        findings.append(_finding("cache_missing", "cache", {"eligible_misses": sum(1 for event in events if event.get("metadata", {}).get("cache_eligible") and not event.get("cache_hit"))}, "Benchmark a scoped prefix cache.", "Unsafe cache boundaries can expose data.", "Disable cache reads and writes."))
    if cache_hits / count < 0.25 and any(event.get("metadata", {}).get("cache_eligible") for event in events):
        findings.append(_finding("low_cache_hit_rate", "cache", {"hit_rate": round(cache_hits / count, 6)}, "Review cache keys and TTL using aggregate hit evidence.", "Broader keys can cross identity boundaries.", "Restore the old key and TTL."))
    if any(event.get("metadata", {}).get("cache_ttl_mismatch") for event in events):
        findings.append(_finding("cache_ttl_mismatch", "cache", {"affected_events": sum(1 for event in events if event.get("metadata", {}).get("cache_ttl_mismatch"))}, "Align cache TTL with measured reuse intervals and freshness requirements.", "A longer TTL can serve stale context.", "Restore the previous TTL."))
    if any(event.get("metadata", {}).get("cache_scope_safe") is False for event in events):
        findings.append(_finding("cache_scope_unsafe", "cache", {"affected_events": sum(1 for event in events if event.get("metadata", {}).get("cache_scope_safe") is False)}, "Partition cache keys by tenant, authorization, model, and relevant configuration.", "Unsafe shared caches can expose cross-user data.", "Disable cache access until scope isolation is restored."))
    if any(event.get("metadata", {}).get("cache_cost_exceeds_saving") for event in events):
        findings.append(_finding("cache_cost_exceeds_saving", "cache", {"affected_events": sum(1 for event in events if event.get("metadata", {}).get("cache_cost_exceeds_saving"))}, "Disable or narrow cache writes whose measured charge exceeds saved reads.", "Removing cache can increase latency.", "Restore prior cache policy."))

    overqualified = 0
    for event in events:
        row = models.resolve(event["model"])
        score = (row or {}).get("capabilities", {}).get("capability_score")
        required = event.get("metadata", {}).get("required_capability_score")
        if score is not None and required is not None and score > required + 1:
            overqualified += 1
    if overqualified:
        findings.append(_finding("overqualified_model", "calls_routing", {"affected_events": overqualified}, "Benchmark the lowest-cost eligible model under the same quality threshold.", "Lower-cost models may fail edge cases.", "Restore the prior model route."))
        simple_count = sum(1 for event in events if event.get("metadata", {}).get("task_complexity") == "low")
        if simple_count:
            findings.append(_finding("simple_task_expensive_model", "calls_routing", {"affected_events": min(simple_count, overqualified)}, "Route simple tasks to the least expensive model that passes the same quality gate.", "Task complexity classifiers can be wrong.", "Restore the former route."))
    high_reasoning = [event for event in events if event.get("metadata", {}).get("task_complexity") == "low" and event["usage"].get("reasoning_tokens", 0) > event["usage"].get("output_tokens", 0)]
    if high_reasoning:
        findings.append(_finding("excessive_reasoning", "calls_routing", {"affected_events": len(high_reasoning)}, "Test a lower reasoning mode with the same quality guard.", "Reasoning reduction can hurt difficult cases.", "Restore prior reasoning effort."))
    if any(event.get("metadata", {}).get("fallback_depth", 0) > 2 for event in events):
        findings.append(_finding("fallback_chain_excess", "calls_routing", {"max_depth": max(event.get("metadata", {}).get("fallback_depth", 0) for event in events)}, "Cap and quality-test fallback depth.", "A shorter chain can reduce availability.", "Restore the previous fallback chain."))
    model_switches = sum(1 for index in range(1, count) if events[index]["model"] != events[index - 1]["model"])
    if model_switches > 1:
        findings.append(_finding("model_switch_rework", "calls_routing", {"model_switches": model_switches}, "Stabilize routing and record why fallback changed models.", "Sticky routing can retain a weak model.", "Restore dynamic switching."))

    repeated_tools = sum(max(0, value - 1) for event in events for value in Counter(event.get("tool_sequence") or []).values())
    if repeated_tools:
        findings.append(_finding("repeated_tool_loop", "tool_agent", {"repeated_tool_calls": repeated_tools}, "Add result-aware loop termination and reuse tool outputs.", "Termination rules can stop legitimate iteration.", "Restore the prior loop limit."))
    if any(event.get("metadata", {}).get("planner_calls", 0) > 1 for event in events):
        findings.append(_finding("planner_reviewer_duplication", "tool_agent", {"affected_events": sum(1 for event in events if event.get("metadata", {}).get("planner_calls", 0) > 1)}, "Reuse the accepted plan and invoke review only on material deltas.", "Fewer reviews can miss regressions.", "Restore planner and reviewer frequency."))
    multi_agent_duplicates = sum(int(event.get("metadata", {}).get("duplicate_agent_tasks", 0)) for event in events)
    if multi_agent_duplicates:
        findings.append(_finding("multi_agent_duplicate", "tool_agent", {"duplicate_agent_tasks": multi_agent_duplicates}, "Assign unique bounded task ownership and reuse completed agent Evidence.", "Over-aggressive deduplication can suppress independent review.", "Restore independent assignments."))
    if any(event.get("metadata", {}).get("repeated_fetch") for event in events):
        findings.append(_finding("repeated_fetch", "tool_agent", {"affected_events": sum(1 for event in events if event.get("metadata", {}).get("repeated_fetch"))}, "Cache immutable fetch results with source binding.", "Stale data can invalidate answers.", "Disable fetch reuse."))
    if any(event.get("metadata", {}).get("large_tool_output_reinjected") for event in events):
        findings.append(_finding("large_tool_output_reinjection", "tool_agent", {"affected_events": sum(1 for event in events if event.get("metadata", {}).get("large_tool_output_reinjected"))}, "Pass structured summaries and exact references instead of full output.", "Summaries can hide details.", "Restore full output injection."))
    if any(event.get("metadata", {}).get("local_compute_eligible") for event in events):
        findings.append(_finding("model_used_for_local_compute", "tool_agent", {"affected_events": sum(1 for event in events if event.get("metadata", {}).get("local_compute_eligible"))}, "Use deterministic local computation and validate its output.", "Local logic needs its own tests.", "Restore the model call."))

    if any(event.get("metadata", {}).get("parallelizable") and event.get("metadata", {}).get("executed_serially") for event in events):
        findings.append(_finding("serial_parallelizable_calls", "infrastructure", {"affected_events": sum(1 for event in events if event.get("metadata", {}).get("parallelizable") and event.get("metadata", {}).get("executed_serially"))}, "Boundedly parallelize independent calls and monitor retry rate.", "Concurrency can trigger limits.", "Restore serial execution."))
    if any(event.get("metadata", {}).get("batch_eligible") and not event.get("batch") for event in events):
        findings.append(_finding("batch_opportunity", "infrastructure", {"affected_events": sum(1 for event in events if event.get("metadata", {}).get("batch_eligible") and not event.get("batch"))}, "Benchmark the Provider's supported batch mode.", "Batch latency may exceed the workload limit.", "Restore synchronous calls."))
    if any(event.get("metadata", {}).get("concurrency_retry") for event in events):
        findings.append(_finding("concurrency_retry_amplification", "infrastructure", {"affected_events": sum(1 for event in events if event.get("metadata", {}).get("concurrency_retry"))}, "Lower concurrency until retry-adjusted throughput improves.", "Lower concurrency can reduce throughput.", "Restore previous concurrency."))
    queue_duplicates = sum(int(event.get("metadata", {}).get("queue_duplicate_count", 0)) for event in events)
    if queue_duplicates:
        findings.append(_finding("queue_duplicate_execution", "infrastructure", {"duplicate_executions": queue_duplicates}, "Bind queue deliveries to idempotent completion receipts.", "Incorrect deduplication can discard legitimate retries.", "Restore the prior queue delivery behavior."))
    if any(event.get("metadata", {}).get("wait_model_occupied") for event in events):
        findings.append(_finding("model_occupied_while_waiting", "infrastructure", {"affected_events": sum(1 for event in events if event.get("metadata", {}).get("wait_model_occupied"))}, "Release model work while waiting on external I/O.", "Resumption requires reliable state.", "Restore the synchronous flow."))
    if failures / count > 0.2:
        findings.append(_finding("failure_cost_spike", "infrastructure", {"failure_rate": round(failures / count, 6)}, "Track cost per successful completion and fix the leading failure class.", "Aggressive rejection can reduce coverage.", "Restore previous failure handling."))
    if latencies and max(latencies) > max(1, median(latencies) * 2):
        findings.append(_finding("latency_spike", "infrastructure", {"median_ms": round(median(latencies), 6), "max_ms": round(max(latencies), 6)}, "Correlate latency spikes with retry, model, and queue evidence.", "Latency routing can increase cost.", "Restore prior latency policy."))
    if tool_calls and any(event.get("metadata", {}).get("rework") for event in events):
        findings.append(_finding("tool_rework_cost", "tool_agent", {"tool_calls": tool_calls, "rework_events": sum(1 for event in events if event.get("metadata", {}).get("rework"))}, "Bind tool outputs to the task and reuse validated results.", "Reusing stale tool results can be incorrect.", "Restore fresh tool execution."))
    return findings
