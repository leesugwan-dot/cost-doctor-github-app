from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .canonical import sha256_json
from .capsules import verify_capsule
from .measurement import classify_measurement


class CodingAgentError(ValueError):
    pass


class CodingAgentRegistry:
    def __init__(self, directory: Path):
        self.rows: dict[str, dict[str, Any]] = {}
        sources = []
        for path in sorted(directory.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("schema") != "costdoctor.coding-agent-registry.v1":
                raise CodingAgentError("CODING_AGENT_REGISTRY_SCHEMA_INVALID")
            for row in payload.get("rows", []):
                agent_id = str(row.get("agent_id", ""))
                if not agent_id or agent_id in self.rows:
                    raise CodingAgentError("CODING_AGENT_ID_INVALID_OR_DUPLICATE")
                self.rows[agent_id] = deepcopy(row)
            sources.append({"name": path.name, "digest": sha256_json(payload)})
        if not sources:
            raise CodingAgentError("CODING_AGENT_REGISTRY_EMPTY")
        self.snapshot = {"sources": sources, "digest": sha256_json(list(self.rows.values()))}

    def resolve(self, agent_id: str) -> dict[str, Any]:
        row = self.rows.get(agent_id)
        if row is None:
            raise CodingAgentError("CODING_AGENT_PROFILE_UNKNOWN")
        return deepcopy(row)


def build_repo_map(files: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for item in files:
        path = str(item.get("path", ""))
        if not path or path.startswith(("/", "\\")) or ".." in Path(path).parts:
            raise CodingAgentError("REPO_MAP_PATH_INVALID")
        rows.append({"path": path.replace("\\", "/"), "size": int(item.get("size", 0)), "role": str(item.get("role", "unknown")), "changed": bool(item.get("changed", False)), "digest": str(item.get("digest", ""))})
    rows.sort(key=lambda row: row["path"])
    return {"schema": "costdoctor.repo-map.v1", "files": rows, "raw_source_included": False, "fingerprint": sha256_json(rows)}


def build_coding_agent_packet(profile: dict[str, Any], task_capsule: dict[str, Any], state_capsule: dict[str, Any], context_capsule: dict[str, Any], evidence_capsule: dict[str, Any], delta_capsule: dict[str, Any], repo_map: dict[str, Any]) -> dict[str, Any]:
    capsules = [task_capsule, state_capsule, context_capsule, evidence_capsule, delta_capsule]
    if not all(verify_capsule(item) for item in capsules):
        raise CodingAgentError("CODING_AGENT_CAPSULE_INVALID")
    allowed = set(task_capsule["allowed_scope"])
    forbidden = set(task_capsule["forbidden_scope"])
    if allowed & forbidden:
        raise CodingAgentError("CODING_AGENT_SCOPE_CONFLICT")
    target_files = sorted(set(task_capsule["target_files"]))
    mapped = {row["path"] for row in repo_map.get("files", [])}
    if set(target_files) - mapped:
        raise CodingAgentError("CODING_AGENT_TARGET_NOT_IN_REPO_MAP")
    body = {"schema": "costdoctor.coding-agent-packet.v1", "agent_id": profile["agent_id"], "task": task_capsule, "state": state_capsule, "context": context_capsule, "evidence": evidence_capsule, "delta": delta_capsule, "repo_map": repo_map, "selective_reads": target_files, "session_reset": deepcopy(profile.get("session_reset") or {}), "usage_contract": deepcopy(profile.get("usage_contract") or {}), "raw_repo_embedded": False}
    body["packet_fingerprint"] = sha256_json(body)
    return body


def collect_coding_agent_usage(profile: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    counters = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    exposed = any(key in counters for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens", "call_count", "retry_count"))
    source = str((profile.get("usage_contract") or {}).get("measurement_source", "AVAILABLE_TOOL_USAGE")) if exposed else "UNKNOWN"
    event = {"provider_reported": False, "measurement_source": source, "usage": {"input_tokens": int(counters.get("input_tokens", 0)), "cached_input_tokens": int(counters.get("cached_input_tokens", 0)), "output_tokens": int(counters.get("output_tokens", 0)), "reasoning_tokens": int(counters.get("reasoning_tokens", 0)), "call_count": int(counters.get("call_count", 1)), "retry_count": int(counters.get("retry_count", 0))}}
    event["measurement"] = classify_measurement(event)
    return event
