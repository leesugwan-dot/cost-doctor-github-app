from __future__ import annotations

from typing import Any

from .pricing import PricingEngine
from .registry import ModelRegistry


def _supports(row: dict[str, Any], requirements: dict[str, Any]) -> bool:
    capabilities = row.get("capabilities") or {}
    for key in requirements.get("required_capabilities", []):
        if capabilities.get(key) is not True:
            return False
    minimum_score = requirements.get("minimum_capability_score")
    score = capabilities.get("capability_score")
    if minimum_score is not None and (score is None or score < minimum_score):
        return False
    context = row.get("context") or {}
    if context.get("input_tokens") is None or context.get("input_tokens", 0) < requirements.get("input_tokens", 0):
        return False
    return True


def advise_routing(
    requirements: dict[str, Any],
    models: ModelRegistry,
    pricing: PricingEngine,
    observed: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    observed = observed or {}
    candidates = []
    for row in models.active_rows():
        if not _supports(row, requirements):
            continue
        model_id = row["canonical_id"]
        provider = row["provider"]
        event = {
            "event_id": f"routing:{provider}:{model_id}",
            "provider": provider,
            "model": model_id,
            "started_at": requirements["pricing_at"],
            "usage": dict(requirements.get("expected_usage") or {}),
            "billed_units": {},
            "batch": bool(requirements.get("batch", False)),
        }
        priced = pricing.price_event(event)
        measurement = observed.get(model_id, {})
        quality = measurement.get("quality")
        latency = measurement.get("latency_p95_ms")
        failure_rate = measurement.get("failure_rate")
        eligible = (
            priced["status"] != "UNKNOWN"
            and quality is not None
            and quality >= requirements.get("quality_threshold", 0)
            and latency is not None
            and latency <= requirements.get("latency_limit_ms", float("inf"))
        )
        candidates.append(
            {
                "provider": provider,
                "model": model_id,
                "status": row["status"],
                "quality": quality,
                "latency_p95_ms": latency,
                "failure_rate": failure_rate,
                "estimated_cost_usd": priced.get("cost_usd"),
                "eligible": eligible,
                "reasoning_modes": (row.get("capabilities") or {}).get("reasoning_modes", []),
                "cache": (row.get("capabilities") or {}).get("cache", "unknown"),
            }
        )
    eligible = [item for item in candidates if item["eligible"]]
    eligible.sort(key=lambda item: (float(item["estimated_cost_usd"]), float(item["latency_p95_ms"]), item["model"]))
    recommended = eligible[0] if eligible else None
    fallback = eligible[1] if len(eligible) > 1 else None
    return {
        "schema": "costdoctor.routing-advice.v1",
        "verdict": "ADVICE_AVAILABLE" if recommended else "BLOCKED",
        "objective": "lowest_total_cost_that_meets_quality_and_latency",
        "requirements": requirements,
        "recommended": recommended,
        "fallback": fallback,
        "recommendation_reason": "lowest measured total cost among Registry candidates that satisfy capability, quality, and latency gates" if recommended else "no candidate has complete capability, known price, quality, and latency Evidence",
        "recommended_reasoning_effort": requirements.get("minimum_reasoning_effort", "lowest_supported"),
        "recommended_cache_policy": "safe_prefix_cache_when_identity_and_ttl_boundaries_are_preserved",
        "candidates": candidates,
        "applied": False,
        "feature_flag_required_for_apply": True,
    }
