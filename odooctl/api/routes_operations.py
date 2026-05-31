"""Operation queue and event streaming routes.

POST /projects/{project}/operations  — enqueue a mutating operation.
GET  /operations/{id}                — fetch operation record.
GET  /operations/{id}/events         — SSE stream of operation events.
POST /operations/{id}/cancel         — cancel a queued/running operation.

Params are redacted via ``odooctl.security.redaction.redact`` before storing.
A capability token scoped to the exact action/environment/project is minted
and embedded in the queue entry; the runner verifies it before executing.

No privileged imports — satisfies the runner contract.
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from odooctl.api.auth import get_principal, require_action
from odooctl.security.rbac import Action

router = APIRouter()

# Map operation kind strings to the RBAC action that gates them.
_KIND_ACTION: dict[str, Action] = {
    "backup": Action.BACKUP,
    "restore": Action.RESTORE,
    "clone": Action.CLONE,
    "deploy": Action.DEPLOY,
    "promote": Action.PROMOTE,
    "env_create": Action.ENV,
    "env_destroy": Action.ENV,
    "update_modules": Action.DEPLOY,
    "rollback": Action.RESTORE,
    "dr_drill": Action.RESTORE,
}


class OperationRequest(BaseModel):
    kind: str
    environment: str
    params: dict[str, Any] = {}


def _load_ctx(request: Request, project: str):
    from odooctl.context import ProjectContext

    reg = request.app.state.registry_loader()
    proj = reg.projects.get(project)
    if proj is None:
        raise HTTPException(status_code=404, detail=f"Project {project!r} not found")
    try:
        return ProjectContext.from_config_path(proj.config, root=proj.path)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _find_op_ctx(request: Request, op_id: str):
    """Search all registered projects for an operation by ID."""
    from odooctl.context import ProjectContext
    from odooctl.operations.store import OperationStore

    reg = request.app.state.registry_loader()
    for proj in reg.projects.values():
        try:
            ctx = ProjectContext.from_config_path(proj.config, root=proj.path)
        except Exception:
            continue
        store = OperationStore(ctx.state_dir)
        try:
            op = store.load(op_id)
            return op, store
        except KeyError:
            continue
    raise HTTPException(status_code=404, detail=f"Operation {op_id!r} not found")


@router.post("/projects/{project}/operations", status_code=202)
def enqueue_operation(
    project: str,
    body: OperationRequest,
    request: Request,
    principal=Depends(get_principal),
):
    from odooctl.api.queue import OperationQueue, QueueEntry
    from odooctl.operations.models import Operation, OperationKind
    from odooctl.operations.store import OperationStore
    from odooctl.security import rbac, tokens
    from odooctl.security.redaction import redact

    ctx = _load_ctx(request, project)

    # Resolve the target environment before authorization so protected-env
    # policy is applied to the actual enqueue target.
    try:
        protected = ctx.config.is_protected(body.environment)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # RBAC check for the specific operation kind
    action = _KIND_ACTION.get(body.kind)
    if action is None:
        raise HTTPException(status_code=400, detail=f"Unknown operation kind: {body.kind!r}")
    try:
        rbac.require(principal, action, protected=protected)
    except rbac.AccessDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    api_key: str = request.app.state.api_key

    # Redact user-supplied params before recording
    params_clean = redact(body.params)

    # Create durable operation record (status=QUEUED)
    try:
        kind_enum = OperationKind(body.kind)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid operation kind: {body.kind!r}")

    op = Operation.create(
        kind=kind_enum,
        project=project,
        environment=body.environment,
        actor=principal.id,
        params_redacted=params_clean if isinstance(params_clean, dict) else {},
    )
    store = OperationStore(ctx.state_dir)
    store.save(op)

    # Mint a short-lived capability token scoped to this exact operation
    cap_token = tokens.mint(
        api_key,
        action=body.kind,
        environment=body.environment,
        project=project,
        ttl_seconds=3600,
        subject=principal.id,
        roles=[role.value for role in principal.roles],
    )

    # Write queue entry
    entry = QueueEntry.create(
        op_id=op.id,
        kind=body.kind,
        project=project,
        environment=body.environment,
        actor=principal.id,
        params_redacted=op.params_redacted,
        token=cap_token,
    )
    OperationQueue(ctx.state_dir).enqueue(entry)

    return {
        "op_id": op.id,
        "kind": op.kind.value,
        "project": project,
        "environment": body.environment,
        "status": op.status.value,
        "created_at": op.created_at,
    }


@router.get("/operations/{op_id}")
def get_operation(
    op_id: str,
    request: Request,
    principal=Depends(require_action(Action.OPERATIONS)),
):
    op, _ = _find_op_ctx(request, op_id)
    return {
        "op_id": op.id,
        "kind": op.kind.value,
        "project": op.project,
        "environment": op.environment,
        "status": op.status.value,
        "actor": op.actor,
        "params_redacted": op.params_redacted,
        "created_at": op.created_at,
        "updated_at": op.updated_at,
        "error": op.error,
        "result_ref": op.result_ref,
    }


@router.get("/operations/{op_id}/events")
def stream_events(
    op_id: str,
    request: Request,
    principal=Depends(require_action(Action.OPERATIONS)),
    max_polls: int = 120,
):
    """Stream operation events as Server-Sent Events.

    Polls until the operation reaches a terminal state or *max_polls* is
    exhausted (default 120 × 0.5 s = 60 s). Pass ``?max_polls=1`` in tests
    to avoid blocking indefinitely on a queued operation.
    """
    from odooctl.operations.models import OperationStatus

    op, store = _find_op_ctx(request, op_id)

    async def _generate():
        seen = 0
        polls = 0
        while True:
            events = store.load_events(op_id)
            for event in events[seen:]:
                yield f"data: {event.to_json()}\n\n"
                seen += 1
            current_op = store.load(op_id)
            if current_op.status in (
                OperationStatus.SUCCEEDED,
                OperationStatus.FAILED,
                OperationStatus.CANCELLED,
            ):
                break
            polls += 1
            if polls >= max_polls:
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(_generate(), media_type="text/event-stream")


@router.post("/operations/{op_id}/cancel", status_code=200)
def cancel_operation(
    op_id: str,
    request: Request,
    principal=Depends(require_action(Action.OPERATIONS)),
):
    from odooctl.api.queue import OperationQueue
    from odooctl.context import ProjectContext
    from odooctl.operations.models import OperationStatus

    op, store = _find_op_ctx(request, op_id)
    if op.status not in (OperationStatus.QUEUED,):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel operation in status {op.status.value!r}",
        )

    # Remove the pending queue file so the runner cannot claim and execute it.
    # Best-effort: if the queue file is already claimed (.running), the runner
    # will re-check the operation status and skip execution.
    reg = request.app.state.registry_loader()
    proj = reg.projects.get(op.project)
    if proj is not None:
        try:
            ctx = ProjectContext.from_config_path(proj.config, root=proj.path)
            OperationQueue(ctx.state_dir).cancel(op_id)
        except Exception:
            pass

    updated = store.update_status(op_id, OperationStatus.CANCELLED)
    return {"op_id": updated.id, "status": updated.status.value}
