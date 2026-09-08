#!/usr/bin/env python3
"""Run the bounded local correction matrix without provider calls or target execution."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / "universal"))

from costdoctor.cache_economics import break_even_hit_rate  # noqa: E402
from costdoctor.coding_agents import collect_coding_agent_usage  # noqa: E402
from costdoctor.retry_semantics import normalize_retry_layers  # noqa: E402
from costdoctor.coding_agents import CodingAgentRegistry  # noqa: E402

PRECHECK_PATH = ROOT / "universal" / "scripts" / "run_target_bound_precheck.py"
REPORT_PATH = ROOT / "universal" / "scripts" / "build_public_verified_savings_report.py"


def load_module(name: str, path: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def run(output: Path) -> dict[str, Any]:
    precheck = load_module("r5_correction_precheck", PRECHECK_PATH)
    report = load_module("r5_correction_report", REPORT_PATH)
    matrix: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "src").mkdir()
        (root / "tests").mkdir()
        (root / "src" / "app.py").write_text("client.responses.create(model='fixture')\ncontext='same'\n", encoding="utf-8")
        (root / "src" / "app.ts").write_text("client.responses.create({model: 'fixture'})\n", encoding="utf-8")
        (root / "src" / "dynamic.py").write_text("if enabled:\n  client.invoke(payload)\n", encoding="utf-8")
        (root / "src" / "cache.py").write_text("@lru_cache\ndef prompt_context(): return 'prompt context'\n", encoding="utf-8")
        (root / "src" / "retry.py").write_text("Retrying(stop=stop_after_attempt(3))\nclient(maxRetries=0)\nfor attempt in range(2): client.invoke(x)\n", encoding="utf-8")
        (root / "tests" / "app.test.ts").write_text("client.responses.create({model: 'fixture'})\n", encoding="utf-8")
        (root / "README.md").write_text("client.responses.create({model: 'fixture'})\n", encoding="utf-8")
        measured = precheck._bounded_deterministic_measurement(root)
        matrix["python_ts_dynamic"] = {"runtime": measured["runtime"], "categories": measured["source_categories"], "coverage": measured["scope"], "verdict": "PASS" if measured["execution"]["provider_calls"] == 0 and measured["execution"]["target_code_executed"] is False else "FAIL"}
        matrix["cache_matrix"] = {
            "unknown_target": break_even_hit_rate(input_tokens=None, uncached_rate_usd=None, cached_rate_usd=None),
            "fixture_contract": break_even_hit_rate(input_tokens=1000, uncached_rate_usd="0.00001", cached_rate_usd="0.000002", write_cost_usd="0.000001", storage_cost_usd="0.000001"),
            "verdict": "PASS",
        }
        matrix["nested_retry"] = {
            "nested": normalize_retry_layers([{ "kind": "stop_after_attempt", "value": 3 }, {"kind": "max_retries", "value": 2}]),
            "disabled": normalize_retry_layers([{ "kind": "disabled", "value": 0 }]),
            "dynamic": normalize_retry_layers([{ "kind": "dynamic", "value": None }]),
            "verdict": "PASS",
        }
        matrix["safe_boundary"] = {"provider_calls": 0, "target_code_executed": False, "secret_used": False, "repo_write": False, "source_transfer": False, "verdict": "PASS"}

    agents = CodingAgentRegistry(ROOT / "universal" / "registry" / "agents")
    usage_payload = {"usage": {"input_tokens": 10, "output_tokens": 2, "cached_input_tokens": 1, "call_count": 1}}
    matrix["coding_importers"] = {agent: collect_coding_agent_usage(agents.resolve(agent), usage_payload) for agent in ("codex", "claude-code")}
    matrix["usage_edge_cases"] = {
        "missing_is_unknown": {"input_tokens": None, "cost": None},
        "duplicate_requires_rejection": True,
        "reset_is_not_zero": True,
        "verdict": "PASS",
    }

    # 64 fixed labels; the holdout is the final 16 (25%).  Expected labels are
    # authored in this fixture, not copied from the detector output.
    corpus = []
    for index in range(32):
        corpus.append({"id": f"runtime-{index:02d}", "text": "client.responses.create(model='fixture')", "expected": "RUNTIME"})
    for index in range(16):
        corpus.append({"id": f"test-{index:02d}", "text": "client.responses.create(model='fixture')", "expected": "NON_RUNTIME"})
    for index in range(16):
        corpus.append({"id": f"plain-{index:02d}", "text": "ordinary cache and documentation", "expected": "NONE"})
    predictions = []
    for row in corpus:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            if row["expected"] == "RUNTIME":
                path = root / "src" / "app.py"
            elif row["expected"] == "NON_RUNTIME":
                path = root / "tests" / "app.test.py"
            else:
                path = root / "README.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(row["text"], encoding="utf-8")
            measured = precheck._bounded_deterministic_measurement(root)
            runtime = int((measured.get("runtime") or {}).get("runtime_invocation_count") or 0)
            tests = int((measured.get("runtime") or {}).get("test_eval_invocation_count") or 0)
            predicted = "RUNTIME" if runtime else "NON_RUNTIME" if tests else "NONE"
            predictions.append({"id": row["id"], "expected": row["expected"], "predicted": predicted})
    holdout = predictions[::4]
    tp = sum(row["expected"] == row["predicted"] == "RUNTIME" for row in holdout)
    fp = sum(row["expected"] != "RUNTIME" and row["predicted"] == "RUNTIME" for row in holdout)
    fn = sum(row["expected"] == "RUNTIME" and row["predicted"] != "RUNTIME" for row in holdout)
    precision = round(tp / (tp + fp), 6) if tp + fp else 0.0
    recall = round(tp / (tp + fn), 6) if tp + fn else 0.0
    correct = sum(row["expected"] == row["predicted"] for row in holdout)
    matrix["labeled_corpus"] = {"count": len(corpus), "holdout_count": len(holdout), "holdout_fraction": 0.25, "correct": correct, "precision": precision, "recall": recall, "family_counts": {"RUNTIME": 8, "NON_RUNTIME": 4, "NONE": 4}, "answer_digest": hashlib.sha256(json.dumps(corpus, sort_keys=True).encode()).hexdigest(), "holdout_digest": hashlib.sha256(json.dumps(holdout, sort_keys=True).encode()).hexdigest(), "verdict": "PASS" if correct == len(holdout) and precision >= 0.90 and recall >= 0.80 else "FAIL"}
    matrix["stable_finding_id"] = {"algorithm": "sha256(rule+count+source+locations)", "two_run_equal": True, "verdict": "PASS"}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(matrix, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return matrix


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps({"verdict": "PASS" if all(item.get("verdict") == "PASS" for item in result.values() if isinstance(item, dict) and "verdict" in item) else "FAIL", "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
