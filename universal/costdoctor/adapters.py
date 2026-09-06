from __future__ import annotations

from copy import deepcopy
from typing import Any

from .measurement import classify_measurement


def _nested(payload: dict[str, Any], *path: str, default: Any = 0) -> Any:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict):
            return default
        value = value.get(key, default)
    return value


class ProviderAdapter:
    adapter_id = "base_v1"

    def __init__(self, provider_config: dict[str, Any] | None = None):
        self.provider_config = provider_config or {}

    def discover_capabilities(self) -> dict[str, Any]:
        return deepcopy(self.provider_config.get("capabilities") or {"status": "unknown"})

    def normalize_usage(self, payload: dict[str, Any]) -> dict[str, float | int]:
        usage = payload.get("usage") or {}
        return {
            "input_tokens": int(usage.get("input_tokens", 0)),
            "output_tokens": int(usage.get("output_tokens", 0)),
            "cached_input_tokens": int(usage.get("cached_input_tokens", 0)),
            "cache_write_tokens": int(usage.get("cache_write_tokens", 0)),
            "reasoning_tokens": int(usage.get("reasoning_tokens", 0)),
            "tool_calls": int(usage.get("tool_calls", 0)),
            "call_count": int(usage.get("call_count", 1)),
            "retry_count": int(usage.get("retry_count", 0)),
        }

    def normalize_errors(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"error_class": payload.get("error_class"), "success": bool(payload.get("success", True))}

    def normalize_cache_usage(self, payload: dict[str, Any]) -> dict[str, Any]:
        usage = self.normalize_usage(payload)
        return {
            "cached_input_tokens": usage["cached_input_tokens"],
            "cache_write_tokens": usage["cache_write_tokens"],
            "cache_hit": bool(payload.get("cache_hit", usage["cached_input_tokens"] > 0)),
        }

    def normalize_reasoning_usage(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"reasoning_tokens": self.normalize_usage(payload)["reasoning_tokens"]}

    def normalize_tool_usage(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"tool_calls": self.normalize_usage(payload)["tool_calls"], "tool_sequence": payload.get("tool_sequence", [])}

    def normalize_latency(self, payload: dict[str, Any]) -> float:
        return float(payload.get("latency_ms", 0))

    def normalize_billing_units(self, payload: dict[str, Any]) -> dict[str, float | int]:
        units = payload.get("billed_units") or {}
        return {str(key): value for key, value in units.items() if isinstance(value, (int, float)) and value >= 0}

    def health_check(self) -> dict[str, Any]:
        return {"status": "PASS", "mode": "OFFLINE_IMPORT", "network_calls": 0, "secret_required": False}

    def normalize(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        usage = self.normalize_usage(payload)
        errors = self.normalize_errors(payload)
        cache = self.normalize_cache_usage(payload)
        event = {
            "schema": "costdoctor.usage-event.v1",
            "event_id": str(payload["event_id"]),
            "workload_id": str(context["workload_id"]),
            "run_id": str(context["run_id"]),
            "sequence": int(payload["sequence"]),
            "provider": str(context.get("provider") or payload.get("provider") or "generic"),
            "model": str(context.get("model") or payload.get("model") or "unknown"),
            "started_at": str(payload["started_at"]),
            "ended_at": str(payload["ended_at"]),
            "success": errors["success"],
            "error_class": errors["error_class"],
            "usage": usage,
            "billed_units": self.normalize_billing_units(payload),
            "provider_reported": bool(payload.get("provider_reported", False)),
            "measurement_source": str(payload.get("measurement_source", "OFFLINE_IMPORT")),
            "provider_response_id": str(payload.get("provider_response_id", "")),
            "tokenizer": deepcopy(payload.get("tokenizer") or {}),
            "latency_ms": self.normalize_latency(payload),
            "cache_hit": cache["cache_hit"],
            "tool_sequence": self.normalize_tool_usage(payload)["tool_sequence"],
            "source_binding": deepcopy(context["source_binding"]),
            "environment_fingerprint": str(context["environment_fingerprint"]),
            "workload_fingerprint": str(context["workload_fingerprint"]),
            "input_fingerprint": str(payload.get("input_fingerprint", "")),
            "context_fingerprint": str(payload.get("context_fingerprint", "")),
            "quality_score": payload.get("quality_score"),
            "metadata": deepcopy(payload.get("metadata") or {}),
            "batch": bool(payload.get("batch", False)),
        }
        event["measurement"] = classify_measurement(event)
        return event


class GenericAdapter(ProviderAdapter):
    adapter_id = "generic_v1"


class OpenAIAdapter(ProviderAdapter):
    adapter_id = "openai_v1"

    def normalize_usage(self, payload: dict[str, Any]) -> dict[str, int]:
        usage = payload.get("usage") or {}
        responses_shape = "input_tokens" in usage or "output_tokens" in usage
        if responses_shape:
            cached = int(_nested(usage, "input_tokens_details", "cached_tokens"))
            cache_write = int(_nested(usage, "input_tokens_details", "cache_write_tokens"))
            input_total = int(usage.get("input_tokens", 0))
            output_total = int(usage.get("output_tokens", 0))
            reasoning = int(_nested(usage, "output_tokens_details", "reasoning_tokens"))
        else:
            cached = int(_nested(usage, "prompt_tokens_details", "cached_tokens"))
            cache_write = 0
            input_total = int(usage.get("prompt_tokens", 0))
            output_total = int(usage.get("completion_tokens", 0))
            reasoning = int(_nested(usage, "completion_tokens_details", "reasoning_tokens"))
        return {
            "input_tokens": max(0, input_total - cached - cache_write),
            "output_tokens": max(0, output_total - reasoning),
            "cached_input_tokens": cached,
            "cache_write_tokens": cache_write,
            "reasoning_tokens": reasoning,
            "tool_calls": int(payload.get("tool_call_count", 0)),
            "call_count": int(payload.get("call_count", 1)),
            "retry_count": int(payload.get("retry_count", 0)),
        }


class AnthropicAdapter(ProviderAdapter):
    adapter_id = "anthropic_v1"

    def normalize_usage(self, payload: dict[str, Any]) -> dict[str, int]:
        usage = payload.get("usage") or {}
        return {
            "input_tokens": int(usage.get("input_tokens", 0)),
            "output_tokens": int(usage.get("output_tokens", 0)),
            "cached_input_tokens": int(usage.get("cache_read_input_tokens", 0)),
            "cache_write_tokens": int(usage.get("cache_creation_input_tokens", 0)),
            "reasoning_tokens": int(usage.get("reasoning_tokens", 0)),
            "tool_calls": int(payload.get("tool_call_count", 0)),
            "call_count": int(payload.get("call_count", 1)),
            "retry_count": int(payload.get("retry_count", 0)),
        }


class GeminiAdapter(ProviderAdapter):
    adapter_id = "gemini_v1"

    def normalize_usage(self, payload: dict[str, Any]) -> dict[str, int]:
        usage = payload.get("usageMetadata") or payload.get("usage") or {}
        cached = int(usage.get("cachedContentTokenCount", 0))
        prompt = int(usage.get("promptTokenCount", 0))
        return {
            "input_tokens": max(0, prompt - cached),
            "output_tokens": int(usage.get("candidatesTokenCount", 0)),
            "cached_input_tokens": cached,
            "cache_write_tokens": 0,
            "reasoning_tokens": int(usage.get("thoughtsTokenCount", 0)),
            "tool_calls": int(payload.get("tool_call_count", 0)),
            "call_count": int(payload.get("call_count", 1)),
            "retry_count": int(payload.get("retry_count", 0)),
        }


class AgnesAdapter(GenericAdapter):
    adapter_id = "agnes_v1"


class OllamaAdapter(ProviderAdapter):
    adapter_id = "ollama_v1"

    def normalize_usage(self, payload: dict[str, Any]) -> dict[str, int]:
        return {
            "input_tokens": int(payload.get("prompt_eval_count", 0)),
            "output_tokens": int(payload.get("eval_count", 0)),
            "cached_input_tokens": int(payload.get("cached_prompt_tokens", 0)),
            "cache_write_tokens": 0,
            "reasoning_tokens": int(payload.get("reasoning_tokens", 0)),
            "tool_calls": int(payload.get("tool_call_count", 0)),
            "call_count": int(payload.get("call_count", 1)),
            "retry_count": int(payload.get("retry_count", 0)),
        }


ADAPTER_TYPES = {
    cls.adapter_id: cls
    for cls in (GenericAdapter, OpenAIAdapter, AnthropicAdapter, GeminiAdapter, AgnesAdapter, OllamaAdapter)
}


def build_adapter(adapter_id: str, provider_config: dict[str, Any] | None = None) -> ProviderAdapter:
    adapter_type = ADAPTER_TYPES.get(adapter_id)
    if adapter_type is None:
        raise ValueError("PROVIDER_ADAPTER_UNKNOWN")
    return adapter_type(provider_config)
