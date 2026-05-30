"""Operation engine — context manager that wraps mutating service calls."""
from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Generator

from odooctl.operations.audit import AuditStore, AuditEntry
from odooctl.operations.locks import EnvironmentLock, LockAcquisitionError
from odooctl.operations.models import (
    Event,
    Operation,
    OperationKind,
    OperationStatus,
    _utcnow,
)
from odooctl.operations.store import OperationStore


class OperationContext:
    """Passed into the `with run_operation(...)` block for event emission."""

    def __init__(self, op: Operation, store: OperationStore) -> None:
        self.op = op
        self._store = store
        self._seq = 0

    def emit(
        self,
        message: str,
        *,
        phase: str = "",
        level: str = "info",
        data: dict | None = None,
    ) -> None:
        event = Event(
            op_id=self.op.id,
            seq=self._seq,
            timestamp=_utcnow(),
            level=level,
            phase=phase,
            message=message,
            data=data or {},
        )
        self._store.append_event(self.op.id, event)
        self._seq += 1


@contextlib.contextmanager
def run_operation(
    store: OperationStore,
    audit: AuditStore,
    *,
    kind: OperationKind,
    project: str,
    environment: str,
    actor: str,
    params_redacted: dict,
    state_dir: Path,
) -> Generator[OperationContext, None, None]:
    """Context manager that wraps a mutating service call as a durable operation.

    Acquires the per-environment lock, transitions the operation through
    QUEUED → RUNNING → SUCCEEDED/FAILED, emits start/end events, and appends
    an audit entry regardless of outcome.
    """
    op = Operation.create(kind, project, environment, actor, params_redacted)
    store.save(op)

    lock = EnvironmentLock(environment, state_dir, op.id)
    try:
        lock.__enter__()
    except LockAcquisitionError as exc:
        op.status = OperationStatus.FAILED
        op.error = f"Could not acquire lock for environment '{environment}'"
        op.updated_at = _utcnow()
        store.save(op)
        store.append_event(
            op.id,
            Event(
                op_id=op.id,
                seq=0,
                timestamp=_utcnow(),
                level="error",
                phase="end",
                message=f"lock acquisition failed: {exc}",
                data={},
            ),
        )
        audit.append(
            AuditEntry(
                actor=actor,
                action=kind.value,
                target=environment,
                params_redacted=params_redacted,
                outcome="failed",
                op_id=op.id,
                timestamp=_utcnow(),
            )
        )
        raise

    op.status = OperationStatus.RUNNING
    op.updated_at = _utcnow()
    store.save(op)

    op_ctx = OperationContext(op, store)
    op_ctx.emit(f"operation started: {kind.value} on {environment}", phase="start")

    outcome = "failed"
    error_msg: str | None = None
    try:
        yield op_ctx
        outcome = "succeeded"
    except Exception as exc:
        error_msg = str(exc)
        raise
    finally:
        lock.__exit__(None, None, None)
        if outcome == "succeeded":
            op_ctx.emit("operation completed", phase="end", level="info")
            store.update_status(op.id, OperationStatus.SUCCEEDED)
        else:
            op_ctx.emit(
                f"operation failed: {error_msg}", phase="end", level="error"
            )
            store.update_status(op.id, OperationStatus.FAILED, error=error_msg)
        audit.append(
            AuditEntry(
                actor=actor,
                action=kind.value,
                target=environment,
                params_redacted=params_redacted,
                outcome=outcome,
                op_id=op.id,
                timestamp=_utcnow(),
            )
        )
