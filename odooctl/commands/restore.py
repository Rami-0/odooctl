"""Restore command — thin wrapper around the restore service."""
from __future__ import annotations

# Re-export service utilities so callers that import from here continue to work.
from odooctl.services.restore import (  # noqa: F401
    resolve_backup_dir,
    sha256_file,
    validate_backup_dir,
    run_restore,
)
from odooctl.services.context import ServiceContext


def execute(environment: str, backup: str = "latest", config_path: str = "odooctl.yml") -> str:
    ctx = ServiceContext.from_config_path(config_path)
    result = run_restore(ctx, environment, backup)
    return result.backup_id
