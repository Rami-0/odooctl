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
from odooctl.operations.audit import AuditStore
from odooctl.operations.engine import run_operation
from odooctl.operations.models import OperationKind
from odooctl.operations.store import OperationStore


def execute(environment: str, config_path: str = "odooctl.yml") -> str:
    ctx = ServiceContext.from_config_path(config_path)
    store = OperationStore(ctx.project.state_dir)
    audit = AuditStore(ctx.project.state_dir)
    result = None
    with run_operation(
        store,
        audit,
        kind=OperationKind.BACKUP,
        project=ctx.project.config.project.name,
        environment=environment,
        actor="cli",
        params_redacted={"environment": environment},
        state_dir=ctx.project.state_dir,
    ) as op_ctx:
        op_ctx.emit("starting backup", phase="backup")
        result = run_backup(ctx, environment)
        op_ctx.emit(f"backup complete: {result.backup_id}", phase="backup")
    return result.backup_id  # type: ignore[union-attr]
