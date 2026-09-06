from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("run_a", type=Path); parser.add_argument("run_b", type=Path); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    left = json.loads((args.run_a / "acceptance.json").read_text(encoding="utf-8")); right = json.loads((args.run_b / "acceptance.json").read_text(encoding="utf-8")); match = left.get("semantic_digest") == right.get("semantic_digest")
    payload = {"schema": "costdoctor.universal-optimizer-fresh-compare.v1", "verdict": "PASS" if match and left.get("local_verdict") == right.get("local_verdict") == "PASS" else "FAIL", "semantic_digest_match": match, "run_a_digest": left.get("semantic_digest"), "run_b_digest": right.get("semantic_digest"), "network_calls": 0, "paid_calls": 0}
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"); print(json.dumps(payload, ensure_ascii=False, sort_keys=True)); return 0 if payload["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
