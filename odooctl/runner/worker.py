"""Privileged runner worker — claims and executes queued operations.

The runner:
1. Loads the registry and iterates registered projects.
2. Claims the oldest pending queue entry (atomic POSIX rename).
3. Verifies the capability token (signature, expiry, scope).
4. Checks the nonce has not been replayed (single-use enforcement).
5. Acquires the per-environment lock.
6. Executes the appropriate service call.
7. Emits operation events and transitions status QUEUED→RUNNING→SUCCEEDED/FAILED.
8. Appends an audit trail entry.

This module is privileged — it imports ``odooctl.adapters`` / ``odooctl.odoo``
transitively via the service layer. It must never be imported by odooctl.api.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

from odooctl.api.queue import OperationQueue, QueueEntry
from odooctl.operations.audit import AuditEntry, AuditStore
from odooctl.operations.engine import OperationContext
from odooctl.operations.locks import EnvironmentLock, LockAcquisitionError
from odooctl.operations.models import (
    OperationKind,
    OperationStatus,
    _utcnow,
)
from odooctl.operations.store import OperationStore
from odooctl.security import rbac, tokens
from odooctl.security.principals import Principal, PrincipalKind, Role
from odooctl.security.tokens import TokenError
from odooctl.adapters.db import make_db_adapter as make_context_db_adapter
from odooctl.adapters.filestore import FilestoreAdapter
from odooctl.migration.rehearse import rehearse_upgrade, UpgradeResult
from odooctl.services.backup import run_backup
from odooctl.services.clone import run_clone
from odooctl.services.context import ServiceContext
from odooctl.services.dr import run_dr_drill

if TYPE_CHECKING:
    from odooctl.registry import Registry


_KIND_ACTION: dict[str, rbac.Action] = {
    "backup": rbac.Action.BACKUP,
    "restore": rbac.Action.RESTORE,
    "clone": rbac.Action.CLONE,
    "deploy": rbac.Action.DEPLOY,
    "promote": rbac.Action.PROMOTE,
    "env_create": rbac.Action.ENV,
    "env_destroy": rbac.Action.ENV,
    "update_modules": rbac.Action.DEPLOY,
    "rollback": rbac.Action.RESTORE,
    "dr_drill": rbac.Action.RESTORE,
    "migrate_rehearsal": rbac.Action.RESTORE,
}


class NonceStore:
    """Tracks consumed capability token nonces to prevent replay attacks.

    Nonces are stored in ``{state_dir}/consumed_nonces.json``.
    The set grows unbounded for now — a TTL-based purge can be added later.
    """

    def __init__(self, state_dir: Path) -> None:
        self._path = state_dir / "consumed_nonces.json"
        state_dir.mkdir(parents=True, exist_ok=True)

    def is_consumed(self, nonce: str) -> bool:
        if not self._path.exists():
            return False
        try:
            return nonce in json.loads(self._path.read_text()).get("nonces", [])
        except Exception:
            return False

    def mark_consumed(self, nonce: str) -> None:
        nonces: list[str] = []
        if self._path.exists():
            try:
                nonces = json.loads(self._path.read_text()).get("nonces", [])
            except Exception:
                pass
        if nonce not in nonces:
            nonces.append(nonce)
        self._path.write_text(json.dumps({"nonces": nonces}))


class RunnerWorker:
    """Claims and executes one queued operation per ``claim_and_run()`` call."""

    def __init__(self, registry: "Registry", api_key: str) -> None:
        self._registry = registry
        self._api_key = api_key

    def claim_and_run(self) -> bool:
        """Claim and execute one operation. Returns True if work was done."""
        for proj_name, proj in self._registry.projects.items():
            from odooctl.context import ProjectContext

            try:
                ctx = ProjectContext.from_config_path(proj.config, root=proj.path)
            except Exception:
                continue

            queue = OperationQueue(ctx.state_dir)
            entry = queue.claim_next()
            if entry is None:
                continue

            self._execute_entry(entry, queue, ctx)
            return True
        return False

    def _execute_entry(self, entry: QueueEntry, queue: OperationQueue, ctx) -> None:
        store = OperationStore(ctx.state_dir)
        audit = AuditStore(ctx.state_dir)
        nonce_store = NonceStore(ctx.state_dir)
        svc_ctx = ServiceContext(project=ctx)

        # Re-check status: the operation may have been cancelled after we claimed
        # the queue entry (post-claim race). Skip execution and clean up.
        try:
            if store.load(entry.op_id).status == OperationStatus.CANCELLED:
                queue.complete(entry.op_id)
                return
        except KeyError:
            pass

        # Verify the capability token
        try:
            payload = tokens.verify(
                self._api_key,
                entry.token,
                action=entry.kind,
                environment=entry.environment,
                project=entry.project,
            )
        except TokenError as exc:
            store.update_status(entry.op_id, OperationStatus.FAILED, error=f"token error: {exc}")
            queue.fail(entry.op_id)
            return

        # Defensive RBAC floor: do not trust queue shape alone. Reconstruct the
        # token-derived principal and enforce the same protected-env floor that
        # the API applied before enqueueing.
        try:
            action = _KIND_ACTION[entry.kind]
            protected = ctx.config.is_protected(entry.environment)
            rbac.require(_principal_from_payload(payload), action, protected=protected)
        except (KeyError, ValueError, rbac.AccessDenied) as exc:
            store.update_status(entry.op_id, OperationStatus.FAILED, error=f"rbac error: {exc}")
            queue.fail(entry.op_id)
            return

        # Single-use nonce check
        nonce = payload.get("nonce", "")
        if nonce_store.is_consumed(nonce):
            store.update_status(
                entry.op_id,
                OperationStatus.FAILED,
                error=f"token nonce already consumed: {nonce}",
            )
            queue.fail(entry.op_id)
            return
        nonce_store.mark_consumed(nonce)

        # Transition to RUNNING and emit start event
        store.update_status(entry.op_id, OperationStatus.RUNNING)
        op = store.load(entry.op_id)
        op_ctx = OperationContext(op, store)
        op_ctx.emit(
            f"operation started: {entry.kind} on {entry.environment}",
            phase="start",
        )

        # Acquire per-environment lock and execute
        lock = EnvironmentLock(entry.environment, ctx.state_dir, entry.op_id)
        outcome = "failed"
        error_msg: str | None = None

        try:
            lock.__enter__()
            try:
                _dispatch(entry, svc_ctx, op_ctx)
                outcome = "succeeded"
            except Exception as exc:
                error_msg = str(exc)
            finally:
                lock.__exit__(None, None, None)
        except LockAcquisitionError as exc:
            error_msg = f"lock acquisition failed: {exc}"

        # Finalise operation status
        if outcome == "succeeded":
            op_ctx.emit("operation completed", phase="end", level="info")
            store.update_status(entry.op_id, OperationStatus.SUCCEEDED)
            queue.complete(entry.op_id)
        else:
            op_ctx.emit(f"operation failed: {error_msg}", phase="end", level="error")
            store.update_status(entry.op_id, OperationStatus.FAILED, error=error_msg)
            queue.fail(entry.op_id)

        audit.append(
            AuditEntry(
                actor=entry.actor,
                action=entry.kind,
                target=entry.environment,
                params_redacted=entry.params_redacted,
                outcome=outcome,
                op_id=entry.op_id,
                timestamp=_utcnow(),
            )
        )

    def run_loop(self, *, once: bool = False) -> None:
        """Process the queue in a loop.

        :param once: If True, process at most one item and return (used by
            ``odooctl runner --once``).
        """
        while True:
            did_work = self.claim_and_run()
            if once:
                return
            if not did_work:
                time.sleep(1)


def _dispatch(entry: QueueEntry, svc_ctx: ServiceContext, op_ctx: OperationContext) -> None:
    """Dispatch a queued entry to the appropriate service call."""
    kind = entry.kind
    env = entry.environment
    params = entry.params_redacted

    if kind == OperationKind.BACKUP.value:
        result = run_backup(svc_ctx, env)
        op_ctx.emit(f"backup complete: {result.backup_id}", phase="backup")

    elif kind == OperationKind.CLONE.value:
        source = params.get("source", "production")
        result = run_clone(svc_ctx, source, env)
        op_ctx.emit(f"clone complete: {result.url}", phase="clone")

    elif kind == OperationKind.DR_DRILL.value:
        cfg = svc_ctx.project.config
        db_adapter = make_context_db_adapter(svc_ctx.project)
        fs_adapter = FilestoreAdapter()

        def healthcheck_fn(url: str) -> bool:
            try:
                from odooctl.odoo.healthcheck import check_url

                check_url(url, timeout=cfg.healthcheck.timeout_seconds, retries=1, interval=1)
                return True
            except Exception:
                return False

        result = run_dr_drill(
            environment=env,
            backups_root=svc_ctx.project.backups_dir,
            db_adapter=db_adapter,
            fs_adapter=fs_adapter,
            healthcheck_fn=healthcheck_fn,
            is_protected_fn=cfg.is_protected,
        )
        if result.status != "success":
            raise RuntimeError(result.message or "DR drill failed")
        op_ctx.emit(f"DR drill complete: {result.backup_id}", phase="dr_drill")

    elif kind == OperationKind.MIGRATE_REHEARSAL.value:
        from odooctl.migration.matrix import supported_paths

        cfg = svc_ctx.project.config
        env_cfg = cfg.env(env)
        db_adapter = make_context_db_adapter(svc_ctx.project)
        target_version = params.get("to", "")
        if not target_version:
            raise ValueError("migrate_rehearsal requires 'to' version in params")
        use_openupgrade = bool(params.get("openupgrade", False))
        keep_throwaway = bool(params.get("keep", False))
        from_version = cfg.project.odoo_version

        matrix_paths = supported_paths(from_version=from_version, to_version=target_version)
        if not matrix_paths:
            raise ValueError(
                f"No supported migration path from {from_version!r} to {target_version!r}; "
                "check the migration matrix for supported paths."
            )
        path_requires_ou = any(p.requires_openupgrade for p in matrix_paths)

        def _upgrade_fn(throwaway_db: str, tgt_ver: str) -> UpgradeResult:
            from odooctl.adapters.docker_compose import DockerComposeAdapter

            compose = DockerComposeAdapter(
                cfg.runtime.compose_file, project_dir=str(svc_ctx.project.root)
            )
            if use_openupgrade:
                from odooctl.migration.openupgrade import openupgrade_db_command

                cmd = openupgrade_db_command(throwaway_db, tgt_ver)
                if cmd is None:
                    raise ValueError(
                        f"OpenUpgrade does not support target version {tgt_ver!r}; "
                        "check PINNED_BRANCHES or remove --openupgrade"
                    )
            else:
                cmd = [
                    "odoo",
                    "--database", throwaway_db,
                    "--update", "all",
                    "--stop-after-init",
                ]
            try:
                compose.exec(cfg.odoo.service, cmd, stream=True)
                return UpgradeResult(ok=True)
            except Exception as exc:
                return UpgradeResult(ok=False, warnings=[str(exc)])

        def _healthcheck_fn(db_name: str) -> bool:
            # Ping the throwaway DB — after --stop-after-init Odoo is not running,
            # so an HTTP check against the source env URL would test the wrong target.
            try:
                db_adapter.ping(db_name)
                return True
            except Exception:
                return False

        report_dir = svc_ctx.project.state_dir / "migration_reports"

        result = rehearse_upgrade(
            source_env=env,
            source_version=from_version,
            target_version=target_version,
            source_db=env_cfg.db_name,
            db_adapter=db_adapter,
            healthcheck_fn=_healthcheck_fn,
            upgrade_fn=_upgrade_fn,
            report_dir=report_dir,
            keep=keep_throwaway,
            requires_openupgrade=path_requires_ou,
            use_openupgrade=use_openupgrade,
        )
        if result.status != "success":
            raise RuntimeError(result.message or "Migration rehearsal failed")
        op_ctx.emit(
            f"migrate rehearsal complete: {env} {result.source_version} → {target_version}",
            phase="migrate_rehearsal",
        )

    else:
        raise ValueError(f"Unsupported operation kind in runner: {kind!r}")


def _principal_from_payload(payload: dict) -> Principal:
    roles_raw = payload.get("roles", [])
    roles: list[Role] = []
    if isinstance(roles_raw, list):
        for role in roles_raw:
            try:
                roles.append(Role(role))
            except ValueError:
                continue

    subject = str(payload.get("sub", "api-client"))
    return Principal(
        id=subject,
        org_id=str(payload.get("org", "default")),
        kind=PrincipalKind.TOKEN,
        roles=frozenset(roles),
        display=subject,
    )
