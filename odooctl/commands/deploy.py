"""Deploy command — thin wrapper around the deploy service."""
from __future__ import annotations

from odooctl.services.context import ServiceContext
from odooctl.services.deploy import run_deploy


def execute(environment: str, branch: str | None = None, config_path: str = "odooctl.yml") -> None:
    ctx = ServiceContext.from_config_path(config_path)
    run_deploy(ctx, environment, branch)
