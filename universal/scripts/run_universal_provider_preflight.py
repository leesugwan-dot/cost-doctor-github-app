#!/usr/bin/env python3
"""Provider-neutral, no-network preflight for the optional Stage 2 actual path."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON_OBJECT_REQUIRED")
    return value


VALID_PRICE_GRADES = {"PROVIDER_PUBLISHED", "CUSTOMER_CONTRACT", "EXPLICIT_ZERO"}


def price_row(root: Path, provider: str | None, model: str | None) -> dict[str, Any] | None:
    if not provider or not model:
        return None
    for path in sorted((root / "pricing").glob("*.json")):
        payload = load(path)
        for row in payload.get("rows", []):
            if row.get("provider") == provider and row.get("model") == model:
                return row
    return None


def validate_price_row(row: dict[str, Any] | None, provider: str | None, model: str | None) -> tuple[bool, list[str]]:
    """Require provider/model/effective-window/source equality before pricing."""
    if not row:
        return False, ["PRICING_ROW_MISSING"]
    failures: list[str] = []
    if row.get("provider") != provider:
        failures.append("PRICING_PROVIDER_MISMATCH")
    if row.get("model") != model:
        failures.append("PRICING_MODEL_MISMATCH")
    if row.get("status") not in {"confirmed", "active"}:
        failures.append("PRICING_ROW_NOT_CURRENT")
    if row.get("price_grade") not in VALID_PRICE_GRADES:
        failures.append("PRICING_GRADE_UNVERIFIED")
    if not str(row.get("source") or "").strip():
        failures.append("PRICING_SOURCE_MISSING")
    if not str(row.get("effective_from") or "").strip():
        failures.append("PRICING_EFFECTIVE_FROM_MISSING")
    if row.get("effective_to"):
        try:
            expiry = datetime.fromisoformat(str(row["effective_to"]).replace("Z", "+00:00"))
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if expiry <= datetime.now(timezone.utc):
                failures.append("PRICING_ROW_EXPIRED")
        except ValueError:
            failures.append("PRICING_EFFECTIVE_TO_INVALID")
    rates = row.get("unit_rates_usd") or {}
    if row.get("price_grade") != "EXPLICIT_ZERO" and rates.get("input_tokens") is None:
        failures.append("INPUT_TOKEN_RATE_MISSING")
    return not failures, failures


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
    confidence = str(contract.get("confidence") or "UNKNOWN").upper()
    registry_root = Path(__file__).resolve().parents[1] / "registry"
    row = price_row(registry_root, provider, model)
    price_valid, pricing_failures = validate_price_row(row, provider, model)
    contract_conflicts = list(contract.get("conflicts") or [])
    identity_status = str(contract.get("provider_identity_status") or "DETECTED")
    if identity_status != "DETECTED":
        contract_conflicts.append(f"PROVIDER_IDENTITY_{identity_status}")
    if contract_conflicts:
        price_valid = False
        pricing_failures.extend(contract_conflicts)
    pricing_status = (row or {}).get("price_grade") if price_valid else "UNKNOWN"
    pricing_evidence = None
    if row and price_valid and pricing_status in VALID_PRICE_GRADES:
        pricing_evidence = {
            "provider": row.get("provider"),
            "model": row.get("model"),
            "price_version": row.get("price_version"),
            "effective_from": row.get("effective_from"),
            "price_grade": pricing_status,
            "source": row.get("source"),
            "unit_rates_usd": row.get("unit_rates_usd") or {},
            "billing_dimension": "input_tokens" if (row.get("unit_rates_usd") or {}).get("input_tokens") is not None else "unknown",
            "provider_model_equal": row.get("provider") == provider and row.get("model") == model,
        }
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
    elif not row or not price_valid or pricing_status not in VALID_PRICE_GRADES:
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
        "provider_confidence": confidence,
        "provider_confidence_evidence": contract.get("confidence_evidence") or {},
        "credential_name": contract.get("credential_name"),
        "base_url": contract.get("base_url"),
        "credential_present": secret_present,
        "credential_source": "TARGET_REPOSITORY_GITHUB_SECRET" if secret_present else "OPTIONAL_NOT_PRESENT",
        "execution_confirmation_valid": False,
        "approved_max_spend_usd": str(approved),
        "hard_cap_usd": "0.05",
        "pricing_status": pricing_status,
        "pricing_evidence": pricing_evidence,
        "pricing_binding": {
            "provider": provider,
            "model": model,
            "pricing_provider": (row or {}).get("provider"),
            "pricing_model": (row or {}).get("model"),
            "strict_equality": bool(price_valid and row and row.get("provider") == provider and row.get("model") == model),
            "validity": price_valid,
            "failures": sorted(set(pricing_failures)),
            "identity_status": identity_status,
        },
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
