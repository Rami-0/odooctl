"""odooctl runner — privileged operation runner.

Reads the global registry, polls registered-project queues, and executes
claimed operations. Must be run as a user with access to Docker, Postgres,
and the project filestore.
"""
from __future__ import annotations

import os


def run(*, once: bool = False, fail_fast: bool = False, api_key: str | None = None) -> None:
    if api_key is None:
        api_key = os.environ.get("ODOOCTL_API_KEY", "")
    if not api_key:
        raise SystemExit(
            "API key is required. Set --api-key or ODOOCTL_API_KEY env var."
        )

    from odooctl.registry import load_registry
    from odooctl.runner.worker import RunnerWorker

    registry = load_registry()
    worker = RunnerWorker(registry=registry, api_key=api_key)
    ok = worker.run_loop(once=once, fail_fast=fail_fast)
    if not ok:
        raise SystemExit(1)
