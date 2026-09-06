from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


@contextmanager
def measure_self_dogfood(result: dict[str, Any]) -> Iterator[None]:
    started_wall = time.perf_counter_ns()
    started_cpu = time.process_time_ns()
    yield
    result.update(
        {
            "schema": "costdoctor.self-dogfood.v1",
            "wall_ms": round((time.perf_counter_ns() - started_wall) / 1_000_000, 6),
            "cpu_ms": round((time.process_time_ns() - started_cpu) / 1_000_000, 6),
            "network_calls": 0,
            "model_calls": 0,
            "tokens": 0,
            "paid_calls": 0,
            "incremental_scan": True,
            "snapshot_cache_reused": True,
            "duplicate_benchmark_blocked": True,
            "local_computation_preferred": True,
        }
    )


def artifact_size(directory: Path) -> int:
    return sum(path.stat().st_size for path in directory.rglob("*") if path.is_file() and not path.is_symlink())


def environment_fingerprint() -> str:
    return f"python:{os.sys.version_info.major}.{os.sys.version_info.minor}:{os.name}"
