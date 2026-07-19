"""odooctl runner — privileged operation runner.

Reads the global registry, polls registered-project queues, and executes
claimed operations. Must be run as a user with access to Docker, Postgres,
and the project filestore.
"""
from __future__ import annotations

import os
import sys


def run(*, once: bool = False, fail_fast: bool = False, api_key: str | None = None) -> None:
    if api_key is None:
        api_key = os.environ.get("ODOOCTL_API_KEY", "")
    if not api_key:
        raise SystemExit(
            "API key is required. Set --api-key or ODOOCTL_API_KEY env var."
        )

    # Key-strength floor (F24): a short HMAC key makes every capability token
    # this runner verifies brute-forceable offline.
    from odooctl.security import tokens

    try:
        tokens.enforce_key_strength(api_key)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)

    from odooctl.registry import load_registry
    from odooctl.runner.worker import RunnerWorker

    registry = load_registry()
    worker = RunnerWorker(registry=registry, api_key=api_key)
    ok = worker.run_loop(once=once, fail_fast=fail_fast)
    if not ok:
        raise SystemExit(1)
