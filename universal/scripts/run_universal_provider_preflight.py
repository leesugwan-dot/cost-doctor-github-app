#!/usr/bin/env python3
"""Provider-neutral, no-network preflight for the optional Stage 2 actual path."""
from __future__ import annotations

import argparse
import json
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON_OBJECT_REQUIRED")
    return value


def price_row(root: Path, provider: str | None, model: str | None) -> dict[str, Any] | None:
    if not provider or not model:
        return None
    for path in sorted((root / "pricing").glob("*.json")):
        payload = load(path)
        for row in payload.get("rows", []):
            if row.get("provider") == provider and row.get("model") == model:
                return row
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-binding", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--approved-max-spend-usd", default="0.04")
    parser.add_argument("--secret-present-env", default="COSTDOCTOR_PROVIDER_SECRET_PRESENT")
    args = parser.parse_args()
    binding = load(args.target_binding)
    contract = dict(binding.get("provider_contract") or {})
    try:
        approved = Decimal(str(args.approved_max_spend_usd))
    except (InvalidOperation, ValueError):
        approved = Decimal("-1")
    cap_ok = Decimal("0") <= approved <= Decimal("0.05")
    provider = contract.get("provider")
    model = contract.get("model")
    registry_root = Path(__file__).resolve().parents[1] / "registry"
    row = price_row(registry_root, provider, model)
    pricing_status = (row or {}).get("price_grade") if row else "UNKNOWN"
    secret_present = os.environ.get(args.secret_present_env, "") == "1"
    if not cap_ok:
        reason = "SPEND_CAP_INVALID"
        verdict = "BLOCKED"
    elif not provider:
        reason = "NO_PROVIDER_DETECTED"
        verdict = "NOT_APPLICABLE"
    elif not model:
        reason = "MODEL_UNRESOLVED"
        verdict = "STRUCTURAL_ONLY"
    elif not secret_present:
        reason = "PROVIDER_SECRET_OPTIONAL_NOT_PRESENT"
        verdict = "STAGE2_CONTINUES"
    elif not row or pricing_status not in {"PROVIDER_PUBLISHED", "CUSTOMER_CONTRACT", "EXPLICIT_ZERO"}:
        reason = "UNKNOWN_PRICE_BLOCKED"
        verdict = "BLOCKED"
    else:
        reason = "READY_FOR_EXACT_CONFIRMATION"
        verdict = "READY"
    result = {
        "schema": "costdoctor.universal-provider-preflight.v1",
        "verdict": verdict,
        "reason": reason,
        "provider": provider,
        "model": model,
        "adapter": contract.get("adapter"),
        "credential_name": contract.get("credential_name"),
        "base_url": contract.get("base_url"),
        "credential_present": secret_present,
        "credential_source": "TARGET_REPOSITORY_GITHUB_SECRET" if secret_present else "OPTIONAL_NOT_PRESENT",
        "execution_confirmation_valid": False,
        "approved_max_spend_usd": str(approved),
        "hard_cap_usd": "0.05",
        "pricing_status": pricing_status,
        "workload_ready": bool((binding.get("workload") or {}).get("ready")),
        "target_repository": binding.get("target_repository"),
        "target_commit": binding.get("target_commit"),
        "target_binding_fingerprint": binding.get("target_fingerprint"),
        "network_calls": 0,
        "paid_calls": 0,
        "stage2_continuation": True,
        "secret_raw_output": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict, "provider": provider, "model": model, "stage2_continuation": True, "paid_calls": 0}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
