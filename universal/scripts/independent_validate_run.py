from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "universal"))

from costdoctor.canonical import canonical_json, sha256_json  # noqa: E402
from costdoctor.validator import validate_packet  # noqa: E402


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Independently revalidate a complete acceptance run in a new process.")
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    results = []
    for packet_path in sorted((args.run / "workloads").glob("*/benchmark_packet.json")):
        packet = read_json(packet_path)
        validation = validate_packet(packet)
        results.append(
            {
                "relative_packet": packet_path.relative_to(args.run).as_posix(),
                "expected": "PASS",
                "actual": validation["verdict"],
                "validator_digest": validation["validator_digest"],
            }
        )
    future_path = args.run / "future_model" / "benchmark_packet_unknown.json"
    future_validation = validate_packet(read_json(future_path))
    results.append(
        {
            "relative_packet": future_path.relative_to(args.run).as_posix(),
            "expected": "BLOCKED",
            "actual": future_validation["verdict"],
            "validator_digest": future_validation["validator_digest"],
            "verified_savings_usd": future_validation["verified_savings_usd"],
        }
    )
    checks = {
        "two_verified_workload_packets": len([item for item in results if item["expected"] == "PASS"]) >= 2,
        "all_expected_verdicts_match": all(item["expected"] == item["actual"] for item in results),
        "unknown_future_savings_blocked": results[-1]["actual"] == "BLOCKED" and results[-1]["verified_savings_usd"] is None,
    }
    result = {
        "schema": "costdoctor.separate-process-independent-validation.v1",
        "run_summary_digest": read_json(args.run / "acceptance_summary.json")["summary_digest"],
        "results": results,
        "checks": checks,
        "verdict": "PASS" if all(checks.values()) else "FAIL",
    }
    result["result_digest"] = sha256_json(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(canonical_json(result) + "\n", encoding="utf-8")
    print(canonical_json({"verdict": result["verdict"], "digest": result["result_digest"]}))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
