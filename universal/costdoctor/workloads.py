from __future__ import annotations

import json
import time
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

from .canonical import sha256_json, utc_now


def load_workload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "costdoctor.benchmark-workload.v1" or not payload.get("items"):
        raise ValueError("WORKLOAD_SCHEMA_INVALID")
    return payload


def workload_binding(spec: dict[str, Any], commit: str, environment_fingerprint: str) -> dict[str, Any]:
    public_inputs = [item["value"] for item in spec["items"]]
    return {
        "goal": spec["goal"],
        "input_fingerprint": sha256_json(public_inputs),
        "quality_criteria": spec["quality_criteria"],
        "latency_limit_ms": spec["latency_limit_ms"],
        "tool_permissions": spec["tool_permissions"],
        "repetitions": spec["repetitions"],
        "environment_fingerprint": environment_fingerprint,
        "workload_fingerprint": sha256_json({key: spec[key] for key in ("id", "kind", "goal", "quality_criteria", "items")}),
        "commit": commit,
    }


def _solve(kind: str, value: Any) -> int:
    if kind == "word_count":
        return len(str(value).split())
    if kind == "integer_sum":
        return sum(int(number) for number in value)
    raise ValueError("WORKLOAD_KIND_UNKNOWN")


def run_workload(
    spec: dict[str, Any],
    strategy: dict[str, Any],
    phase: str,
    repetition: int,
    commit: str,
    environment_fingerprint: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    binding = workload_binding(spec, commit, environment_fingerprint)
    run_id = f"{spec['id']}:{phase}:{repetition}:{uuid.uuid4().hex[:12]}"
    raw: list[dict[str, Any]] = []
    seen_context = False
    for sequence, item in enumerate(spec["items"]):
        started = utc_now()
        start_ns = time.perf_counter_ns()
        actual = _solve(spec["kind"], item["value"])
        latency_ms = max(0.001, (time.perf_counter_ns() - start_ns) / 1_000_000)
        quality = 1.0 if actual == item["expected"] else 0.0
        value_tokens = max(1, len(json.dumps(item["value"], ensure_ascii=False).encode("utf-8")) // 4)
        output_tokens = max(1, len(str(actual)))
        context_tokens = int(strategy.get("system_context_tokens", 0))
        retries = int(strategy.get("retry_count", 0))
        calls = 1 + retries
        cache_enabled = bool(strategy.get("cache_enabled", False))
        cache_hit = cache_enabled and seen_context
        if cache_hit:
            input_tokens = value_tokens * calls
            cached_tokens = context_tokens * calls
            cache_write_tokens = 0
        else:
            input_tokens = (value_tokens + context_tokens) * calls
            cached_tokens = 0
            cache_write_tokens = context_tokens if cache_enabled else 0
        seen_context = True
        metadata = {
            "task_complexity": "low",
            "required_capability_score": int(strategy.get("required_capability_score", 1)),
            "max_output_tokens": int(strategy.get("max_output_tokens", 0)),
            "cache_eligible": context_tokens > 0,
            "summary_used": bool(strategy.get("summary_used", True)),
            "conversation_turns": 20 if not strategy.get("summary_used", True) else 3,
            "full_history_reinjected": not bool(strategy.get("summary_used", True)),
            "idempotency_key": None if retries else sha256_json({"run": run_id, "sequence": sequence}),
            "batch_eligible": True,
            "parallelizable": True,
            "executed_serially": True,
            "local_compute_eligible": True,
            "rework": retries > 0,
        }
        raw.append(
            {
                "event_id": f"{run_id}:{sequence}",
                "sequence": sequence,
                "started_at": started,
                "ended_at": utc_now(),
                "success": quality == 1.0,
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens * calls,
                    "cached_input_tokens": cached_tokens,
                    "cache_write_tokens": cache_write_tokens,
                    "reasoning_tokens": int(strategy.get("reasoning_tokens", 0)) * calls,
                    "tool_calls": 0,
                    "call_count": calls,
                    "retry_count": retries,
                },
                "latency_ms": latency_ms,
                "provider_reported": False,
                "measurement_source": "LOCAL_DETERMINISTIC_ACTUAL_RUN",
                "input_fingerprint": sha256_json(item["value"]),
                "context_fingerprint": sha256_json({"workload": spec["id"], "context_tokens": context_tokens}),
                "quality_score": quality,
                "cache_hit": cache_hit,
                "metadata": metadata,
            }
        )
    context = {
        "workload_id": spec["id"],
        "run_id": run_id,
        "provider": strategy["provider"],
        "model": strategy["model"],
        "source_binding": {"commit": commit, "tree_state": "controlled-apply-candidate"},
        "environment_fingerprint": environment_fingerprint,
        "workload_fingerprint": binding["workload_fingerprint"],
    }
    return raw, context


def deterministic_metrics_fingerprint(metrics: dict[str, Any]) -> str:
    stable = deepcopy(metrics)
    for key in ("latency_p50_ms", "latency_p95_ms"):
        stable.pop(key, None)
    return sha256_json(stable)
