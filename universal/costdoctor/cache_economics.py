"""Offline cache economics helpers.

The helper never invents a hit rate for a target repository.  It only computes
the break-even threshold when a fixture or an imported provider contract
supplies every billing dimension explicitly.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def _decimal(value: Any) -> Decimal | None:
    try:
        if value is None:
            return None
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def break_even_hit_rate(*, input_tokens: int | None, uncached_rate_usd: Any, cached_rate_usd: Any, write_cost_usd: Any = 0, storage_cost_usd: Any = 0) -> dict[str, Any]:
    tokens = int(input_tokens or 0)
    uncached = _decimal(uncached_rate_usd)
    cached = _decimal(cached_rate_usd)
    write = _decimal(write_cost_usd)
    storage = _decimal(storage_cost_usd)
    if tokens <= 0 or uncached is None or cached is None or write is None or storage is None:
        return {"status": "UNKNOWN", "reason": "missing pricing/cache dimension", "break_even_hit_rate": None}
    benefit = (uncached - cached) * Decimal(tokens)
    fixed = write + storage
    if benefit <= 0:
        return {"status": "NOT_ECONOMIC", "reason": "cached unit cost is not lower", "break_even_hit_rate": None}
    threshold = fixed / benefit
    return {"status": "AVAILABLE", "break_even_hit_rate": str(threshold.quantize(Decimal('0.000001'))), "uncached_cost_per_request_usd": str((uncached * Decimal(tokens)).quantize(Decimal('0.000000001'))), "cached_cost_per_request_usd": str((cached * Decimal(tokens)).quantize(Decimal('0.000000001'))), "fixed_cost_usd": str(fixed)}
