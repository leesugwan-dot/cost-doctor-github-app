#!/usr/bin/env python3
import argparse
import json
from decimal import Decimal, InvalidOperation


def money(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("BUDGET_INVALID") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError("BUDGET_INVALID")
    return parsed.quantize(Decimal("0.000001"))


def evaluate(limit_usd: Decimal, spent_usd: Decimal, next_max_usd: Decimal):
    projected = spent_usd + next_max_usd
    if limit_usd <= 0:
        return {"status": "BLOCK_BUDGET", "code": "BUDGET_NOT_APPROVED", "projected_usd": str(projected)}
    if projected > limit_usd:
        return {"status": "BLOCK_BUDGET", "code": "BUDGET_LIMIT_EXCEEDED", "projected_usd": str(projected)}
    return {
        "status": "ALLOW_WITHIN_APPROVED_BUDGET",
        "code": "BUDGET_OK",
        "projected_usd": str(projected),
        "remaining_after_max_usd": str(limit_usd - projected),
    }


def main():
    parser = argparse.ArgumentParser(description="CostDoctor preflight budget guard. Does not call any provider.")
    parser.add_argument("--limit-usd", required=True)
    parser.add_argument("--spent-usd", required=True)
    parser.add_argument("--next-max-usd", required=True)
    args = parser.parse_args()
    try:
        result = evaluate(money(args.limit_usd), money(args.spent_usd), money(args.next_max_usd))
    except ValueError as exc:
        result = {"status": "BLOCK_BUDGET", "code": str(exc)}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "ALLOW_WITHIN_APPROVED_BUDGET" else 2


if __name__ == "__main__":
    raise SystemExit(main())
