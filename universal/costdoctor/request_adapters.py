from __future__ import annotations

from copy import deepcopy
from typing import Any

from .canonical import canonical_json


REQUEST_PROFILES = {
    "openai": {"input_key": "input", "max_output_key": "max_output_tokens", "reasoning_key": "reasoning", "cache_key": "prompt_cache_key"},
    "openai-compatible": {"input_key": "input", "max_output_key": "max_output_tokens", "reasoning_key": "reasoning", "cache_key": "prompt_cache_key"},
    "anthropic": {"input_key": "messages", "max_output_key": "max_tokens", "reasoning_key": "thinking", "cache_key": None},
    "gemini": {"input_key": "contents", "max_output_key": "maxOutputTokens", "reasoning_key": "thinkingConfig", "cache_key": "cachedContent"},
    "agnes": {"input_key": "input", "max_output_key": "max_output_tokens", "reasoning_key": "reasoning", "cache_key": "cache_key"},
    "ollama": {"input_key": "prompt", "max_output_key": "num_predict", "reasoning_key": None, "cache_key": None},
}


class RequestAdapterError(ValueError):
    pass


def build_llm_request(provider: str, model: str, context_capsule: dict[str, Any], *, max_output_tokens: int, reasoning_effort: str | None = None, cache_key: str | None = None, structured_output: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = REQUEST_PROFILES.get(provider)
    if profile is None:
        raise RequestAdapterError("REQUEST_PROVIDER_PROFILE_UNKNOWN")
    if not model or max_output_tokens <= 0:
        raise RequestAdapterError("REQUEST_CONTROL_INVALID")
    payload: dict[str, Any] = {"model": model}
    serialized = canonical_json(context_capsule)
    input_key = profile["input_key"]
    if provider == "anthropic":
        payload[input_key] = [{"role": "user", "content": serialized}]
    elif provider == "gemini":
        payload[input_key] = [{"role": "user", "parts": [{"text": serialized}]}]
    else:
        payload[input_key] = serialized
    payload[profile["max_output_key"]] = int(max_output_tokens)
    if reasoning_effort and profile["reasoning_key"]:
        payload[profile["reasoning_key"]] = {"effort": reasoning_effort}
    if cache_key and profile["cache_key"]:
        payload[profile["cache_key"]] = cache_key
    if structured_output:
        payload["response_format"] = deepcopy(structured_output)
    return {"schema": "costdoctor.llm-request-envelope.v1", "provider": provider, "model": model, "request": payload, "controls": {"max_output_tokens": int(max_output_tokens), "reasoning_effort": reasoning_effort, "cache_key_supplied": bool(cache_key), "network_executed": False}}
