from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .canonical import decimal_text
from .registry import PricingRegistry


TOKEN_UNITS = (
    "input_tokens",
    "output_tokens",
    "cached_input_tokens",
    "cache_write_tokens",
    "reasoning_tokens",
)


class PricingEngine:
    def __init__(self, registry: PricingRegistry):
        self.registry = registry

    def price_event(self, event: dict[str, Any]) -> dict[str, Any]:
        snapshot = self.registry.select(event["provider"], event["model"], event["started_at"])
        if snapshot is None or snapshot.get("status") not in {"confirmed", "user_defined", "explicit_zero"}:
            return self._unknown(event, "PRICE_SNAPSHOT_UNAVAILABLE")
        rates = snapshot.get("unit_rates_usd")
        if not isinstance(rates, dict):
            return self._unknown(event, "PRICE_RATES_UNAVAILABLE", snapshot)

        usage = event["usage"]
        breakdown: dict[str, str] = {}
        total = Decimal("0")
        for unit in TOKEN_UNITS:
            quantity = Decimal(str(usage.get(unit, 0)))
            if quantity == 0:
                continue
            if rates.get(unit) is None:
                return self._unknown(event, f"UNKNOWN_BILLED_DIMENSION:{unit}", snapshot)
            charge = quantity * Decimal(str(rates[unit])) / Decimal("1000000")
            total += charge
            breakdown[unit] = decimal_text(charge)

        tool_calls = Decimal(str(usage.get("tool_calls", 0)))
        if tool_calls:
            if rates.get("tool_calls") is None:
                return self._unknown(event, "UNKNOWN_BILLED_DIMENSION:tool_calls", snapshot)
            charge = tool_calls * Decimal(str(rates["tool_calls"]))
            total += charge
            breakdown["tool_calls"] = decimal_text(charge)

        for unit, quantity_value in (event.get("billed_units") or {}).items():
            quantity = Decimal(str(quantity_value))
            rate = (snapshot.get("custom_unit_rates_usd") or {}).get(unit)
            if quantity and rate is None:
                return self._unknown(event, f"UNKNOWN_BILLED_DIMENSION:{unit}", snapshot)
            if quantity:
                charge = quantity * Decimal(str(rate))
                total += charge
                breakdown[f"custom:{unit}"] = decimal_text(charge)

        if event.get("batch"):
            discount = Decimal(str(snapshot.get("batch_discount_fraction", 0)))
            if discount < 0 or discount >= 1:
                return self._unknown(event, "BATCH_DISCOUNT_INVALID", snapshot)
            total *= Decimal("1") - discount

        minimum = Decimal(str(snapshot.get("request_minimum_usd", 0)))
        total = max(total, minimum)
        decimals = int(snapshot.get("rounding_decimals", 9))
        quantum = Decimal(1).scaleb(-decimals)
        total = total.quantize(quantum, rounding=ROUND_HALF_UP)
        return {
            "status": "MEASURED_PRICE_APPLIED",
            "event_id": event["event_id"],
            "cost_usd": decimal_text(total),
            "breakdown": breakdown,
            "pricing_snapshot": snapshot,
            "pricing_snapshot_digest": snapshot["snapshot_digest"],
        }

    @staticmethod
    def _unknown(event: dict[str, Any], reason: str, snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "status": "UNKNOWN",
            "event_id": event["event_id"],
            "cost_usd": None,
            "reason": reason,
            "pricing_snapshot": snapshot,
            "pricing_snapshot_digest": snapshot.get("snapshot_digest") if snapshot else None,
        }
