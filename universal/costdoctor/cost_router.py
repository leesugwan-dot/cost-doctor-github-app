from __future__ import annotations

from decimal import Decimal
from typing import Any

from .measurement import MEASUREMENT_GRADES


ROUTE_LEVELS = {"deterministic": 0, "local": 1, "agnes_or_low_cost": 2, "mid": 3, "high": 4}


def choose_execution_route(candidates: list[dict[str, Any]], quality_threshold: float) -> dict[str, Any]:
    evaluated = []
    for row in candidates:
        route_class = str(row.get("route_class", ""))
        level = ROUTE_LEVELS.get(route_class)
        quality = row.get("quality")
        price_status = str(row.get("price_status", "UNKNOWN"))
        grade = str(row.get("measurement_grade", "UNKNOWN"))
        eligible = level is not None and row.get("capability_match") is True and quality is not None and float(quality) >= quality_threshold and (route_class in {"deterministic", "local"} or price_status == "KNOWN") and grade in MEASUREMENT_GRADES and MEASUREMENT_GRADES[grade] > 0
        evaluated.append({**row, "route_level": level, "eligible": eligible})
    eligible_rows = [row for row in evaluated if row["eligible"]]
    eligible_rows.sort(key=lambda row: (int(row["route_level"]), Decimal(str(row.get("cost_per_success_usd", "0"))), float(row.get("latency_ms", 0)), str(row.get("id", ""))))
    recommended = eligible_rows[0] if eligible_rows else None
    return {"schema": "costdoctor.cost-aware-route.v1", "objective": "minimum_total_cost_per_success_subject_to_quality", "recommended": recommended, "candidates": evaluated, "escalation_allowed_only_after_quality_failure": True, "execution_authorized": False, "verdict": "PASS" if recommended else "NEEDS_EVIDENCE"}
