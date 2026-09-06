from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .canonical import canonical_json
from .evidence import UsageImporter, load_json_or_jsonl
from .pricing import PricingEngine
from .registry import ModelRegistry, PricingRegistry, ProviderRegistry
from .validator import validate_packet


UNIVERSAL = Path(__file__).resolve().parents[1]


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(payload) + "\n", encoding="utf-8")


def _usage_import(args: argparse.Namespace) -> int:
    models = ModelRegistry(UNIVERSAL / "registry" / "models")
    providers = ProviderRegistry(UNIVERSAL / "registry" / "providers")
    pricing = PricingEngine(PricingRegistry(UNIVERSAL / "registry" / "pricing"))
    records = load_json_or_jsonl(args.input)
    evidence = UsageImporter(models, providers).normalize_records(
        records,
        {
            "workload_id": args.workload,
            "run_id": args.run_id,
            "provider": args.provider,
            "model": args.model,
            "source_binding": {"commit": args.commit},
            "environment_fingerprint": args.environment,
            "workload_fingerprint": args.workload_fingerprint,
        },
    )
    result = {
        "schema": "costdoctor.offline-usage-import-result.v1",
        "evidence": evidence,
        "prices": [pricing.price_event(event) for event in evidence["events"]],
        "network_calls": 0,
        "provider_secret_used": False,
    }
    _write(args.output, result)
    unknown = any(item["status"] == "UNKNOWN" for item in result["prices"])
    print(canonical_json({"status": "UNKNOWN" if unknown else "PASS", "output": str(args.output)}))
    return 2 if unknown else 0


def _validate(args: argparse.Namespace) -> int:
    packet = json.loads(args.input.read_text(encoding="utf-8"))
    result = validate_packet(packet, max_age_seconds=args.max_age_seconds)
    _write(args.output, result)
    print(canonical_json({"verdict": result["verdict"], "output": str(args.output)}))
    return 0 if result["verdict"] == "PASS" else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CostDoctor Universal offline evidence tools")
    sub = parser.add_subparsers(dest="command", required=True)
    usage = sub.add_parser("usage-import", help="Normalize and price a JSON/JSONL usage export offline")
    usage.add_argument("--input", type=Path, required=True)
    usage.add_argument("--output", type=Path, required=True)
    usage.add_argument("--provider", required=True)
    usage.add_argument("--model", required=True)
    usage.add_argument("--workload", required=True)
    usage.add_argument("--run-id", required=True)
    usage.add_argument("--commit", required=True)
    usage.add_argument("--environment", required=True)
    usage.add_argument("--workload-fingerprint", required=True)
    usage.set_defaults(handler=_usage_import)
    validate = sub.add_parser("validate", help="Independently validate a benchmark packet")
    validate.add_argument("--input", type=Path, required=True)
    validate.add_argument("--output", type=Path, required=True)
    validate.add_argument("--max-age-seconds", type=int, default=3600)
    validate.set_defaults(handler=_validate)
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
