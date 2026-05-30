"""Backup command — thin wrapper around the backup service."""
from __future__ import annotations


# Re-export service utilities so callers that import from here continue to work.
from odooctl.services.backup import (  # noqa: F401
    git_commit,
    prune_backups,
    redact_config_snapshot,
    run_backup,
)
from odooctl.services.context import ServiceContext


def execute(environment: str, config_path: str = "odooctl.yml") -> str:
    ctx = ServiceContext.from_config_path(config_path)
    result = run_backup(ctx, environment)
    return result.backup_id
