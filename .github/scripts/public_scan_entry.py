#!/usr/bin/env python3
"""Public scan entrypoint with a repository-owner rate-limit exemption.

The public beta keeps its normal per-user limit for everyone except the owner
of the CostDoctor repository that is running this workflow. The owner is
resolved from ``GITHUB_REPOSITORY`` at runtime; no username is hard-coded.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("costdoctor_public_scan", HERE / "public_scan.py")
public_scan = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(public_scan)
_BASE_ENFORCE_RATE_LIMIT = public_scan.enforce_rate_limit


def is_repository_owner(repository: str, user: str) -> bool:
    """Return True only when the issue author matches the repository owner."""
    if not repository or "/" not in repository or not user:
        return False
    owner = repository.split("/", 1)[0].strip()
    return bool(owner) and owner.casefold() == user.strip().casefold()


def enforce_rate_limit(repository: str, user: str, issue_number: int, token: str):
    """Bypass only the repository owner; preserve the normal limiter otherwise."""
    if is_repository_owner(repository, user):
        return None
    return _BASE_ENFORCE_RATE_LIMIT(repository, user, issue_number, token)


def main() -> int:
    public_scan.enforce_rate_limit = enforce_rate_limit
    return int(public_scan.main())


if __name__ == "__main__":
    sys.exit(main())
