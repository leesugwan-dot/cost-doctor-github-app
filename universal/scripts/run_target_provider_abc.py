#!/usr/bin/env python3
"""Compatibility entrypoint delegating to the provider-neutral runner.

The former target-specific name is retained for older callers, but all
provider/model/secret/workload selection now comes from the target binding and
Registry/Adapter layer.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_provider_abc as generic  # noqa: E402
import run_universal_provider_preflight as preflight  # noqa: E402


def main() -> int:
    if "--preflight-only" in sys.argv:
        sys.argv = [arg for arg in sys.argv if arg != "--preflight-only"]
        binding = Path(sys.argv[sys.argv.index("--target-binding") + 1])
        output = Path(sys.argv[sys.argv.index("--output") + 1])
        cap = sys.argv[sys.argv.index("--approved-max-spend-usd") + 1] if "--approved-max-spend-usd" in sys.argv else "0.04"
        sys.argv = ["run_universal_provider_preflight.py", "--target-binding", str(binding), "--output", str(output / "preflight.json"), "--approved-max-spend-usd", cap]
        return preflight.main()
    if "--secret-env" not in sys.argv:
        sys.argv.extend(["--secret-env", "COSTDOCTOR_PROVIDER_SECRET"])
    return generic.main()


if __name__ == "__main__":
    raise SystemExit(main())
