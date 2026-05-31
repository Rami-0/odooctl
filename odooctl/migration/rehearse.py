"""Upgrade rehearsal service.

Safety contract
---------------
* The throwaway DB name is always distinct from the source DB name (guarded at entry).
* ``db_adapter.dump()`` is read-only on the source — it never modifies the source DB.
* All writes target *throwaway_db* only; the production DB and filestore are untouched.
* The throwaway DB is always dropped in the ``finally`` block unless ``keep=True``.
* A JSON report is always saved to *report_dir* — even on failure — when provided.
* ``healthcheck_fn`` receives the throwaway DB name (not the source env public URL) so
  it validates the upgraded DB, not the live source environment.
* When the matrix marks a path ``requires_openupgrade`` and ``use_openupgrade`` is
  ``False``, the rehearsal fails immediately rather than running a standard
  ``odoo --update all`` that cannot perform a real cross-major upgrade.
"""
from __future__ import annotations

import json
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class UpgradeResult:
    ok: bool
    log_ref: str | None = None
    failed_modules: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    installed_after: list[str] = field(default_factory=list)


@dataclass
class RehearsalReport:
    status: str           # "success" | "failed"
    source_env: str
    source_version: str
    target_version: str
    installed_modules: list[str]
    failed_modules: list[str]
    warnings: list[str]
    duration_seconds: float
    healthcheck_status: str   # "passed" | "failed" | "skipped"
    log_path: str | None
    cleanup_status: str       # "cleaned" | "kept" | "cleanup_failed"
    next_actions: list[str]
    message: str | None = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "source_env": self.source_env,
            "source_version": self.source_version,
            "target_version": self.target_version,
            "installed_modules": self.installed_modules,
            "failed_modules": self.failed_modules,
            "warnings": self.warnings,
            "duration_seconds": self.duration_seconds,
            "healthcheck_status": self.healthcheck_status,
            "log_path": self.log_path,
            "cleanup_status": self.cleanup_status,
            "next_actions": self.next_actions,
            "message": self.message,
        }


def rehearse_upgrade(
    *,
    source_env: str,
    source_version: str,
    target_version: str,
    source_db: str,
    db_adapter,
    healthcheck_fn: Callable[[str], bool],
    upgrade_fn: Callable[[str, str], UpgradeResult],
    report_dir: Path | None = None,
    keep: bool = False,
    throwaway_suffix: str = "_mig_rehearsal",
    requires_openupgrade: bool = False,
    use_openupgrade: bool = False,
) -> RehearsalReport:
    """Run an upgrade rehearsal against a throwaway copy of *source_db*.

    :param source_env: Name of the source environment (used in the report).
    :param source_version: Current Odoo version (e.g. ``"17.0"``).
    :param target_version: Target Odoo version (e.g. ``"18.0"``).
    :param source_db: Postgres database name of the source environment.
    :param db_adapter: Injectable adapter (must implement dump/restore/drop/drop_create).
    :param healthcheck_fn: Called after the upgrade with the *throwaway DB name*; returns
        ``True`` if the upgraded database is healthy (e.g. a psql ping).  Must target the
        throwaway DB, not the source environment's public URL.
    :param upgrade_fn: Runs the Odoo upgrade on *throwaway_db*; returns :class:`UpgradeResult`.
    :param report_dir: Directory where the JSON report is written (created if absent).
    :param keep: Leave the throwaway DB intact after rehearsal (useful for debugging).
    :param throwaway_suffix: Suffix appended to *source_db* to form the throwaway DB name.
    :param requires_openupgrade: ``True`` when the migration matrix marks this path as
        requiring OpenUpgrade.  If ``True`` and ``use_openupgrade`` is ``False``, the
        rehearsal fails immediately with a clear message rather than running a standard
        ``odoo --update all`` that cannot perform a real cross-major upgrade.
    :param use_openupgrade: ``True`` when the caller's *upgrade_fn* uses OpenUpgrade.
    """
    throwaway_db = f"{source_db}{throwaway_suffix}"
    if throwaway_db == source_db:
        raise RuntimeError(
            f"Throwaway DB name {throwaway_db!r} must differ from source DB "
            f"{source_db!r}; use a non-empty throwaway_suffix."
        )

    # Early exit: path requires OpenUpgrade but caller did not request it.
    # Running odoo --update all on a throwaway clone cannot perform a real cross-major
    # upgrade, so claiming success would be misleading.
    if requires_openupgrade and not use_openupgrade:
        msg = (
            f"Upgrade path {source_version} → {target_version} requires OpenUpgrade. "
            "Re-run with --openupgrade (and ensure the OpenUpgrade container is set up)."
        )
        report = RehearsalReport(
            status="failed",
            source_env=source_env,
            source_version=source_version,
            target_version=target_version,
            installed_modules=[],
            failed_modules=[],
            warnings=[],
            duration_seconds=0.0,
            healthcheck_status="skipped",
            log_path=None,
            cleanup_status="cleaned",
            next_actions=[
                f"Re-run: odooctl migrate rehearse --env {source_env} "
                f"--to {target_version} --openupgrade",
                "Ensure the OpenUpgrade container is set up per docs/migration.md.",
            ],
            message=msg,
        )
        _save_report_to_dir(report, report_dir)
        return report

    start = time.monotonic()
    status = "failed"
    message: str | None = None
    failed_modules: list[str] = []
    warnings: list[str] = []
    installed_modules: list[str] = []
    healthcheck_status = "skipped"
    log_path: str | None = None
    cleanup_status = "cleaned"
    tmp_dump: Path | None = None

    try:
        # Step 1 — clone source DB into throwaway via dump → restore.
        # dump() is a read-only pg_dump on the source; restore() targets throwaway_db only.
        with tempfile.NamedTemporaryFile(
            prefix="odooctl-mig-", suffix=".dump", delete=False
        ) as tmp:
            tmp_dump = Path(tmp.name)

        db_adapter.dump(source_db, tmp_dump)
        db_adapter.restore(throwaway_db, tmp_dump)

        # Step 2 — run the upgrade against the throwaway DB.
        upgrade_result = upgrade_fn(throwaway_db, target_version)
        log_path = upgrade_result.log_ref
        failed_modules = upgrade_result.failed_modules
        warnings = upgrade_result.warnings
        installed_modules = upgrade_result.installed_after

        if not upgrade_result.ok:
            message = "Upgrade command failed; see log_path for details."
        else:
            # Step 3 — healthcheck: ping the throwaway DB (not the source env URL).
            # After --stop-after-init Odoo is not running, so an HTTP check is meaningless;
            # a DB ping confirms the upgraded schema is accessible.
            ok = healthcheck_fn(throwaway_db)
            healthcheck_status = "passed" if ok else "failed"
            if ok:
                status = "success"
            else:
                message = "Healthcheck failed after upgrade."

    except Exception as exc:
        message = str(exc)
        status = "failed"
    finally:
        if tmp_dump is not None:
            tmp_dump.unlink(missing_ok=True)
        if keep:
            cleanup_status = "kept"
        else:
            try:
                db_adapter.drop(throwaway_db)
            except Exception:
                cleanup_status = "cleanup_failed"

    duration = round(time.monotonic() - start, 2)
    next_actions = _build_next_actions(status, failed_modules, warnings, target_version)

    report = RehearsalReport(
        status=status,
        source_env=source_env,
        source_version=source_version,
        target_version=target_version,
        installed_modules=installed_modules,
        failed_modules=failed_modules,
        warnings=warnings,
        duration_seconds=duration,
        healthcheck_status=healthcheck_status,
        log_path=log_path,
        cleanup_status=cleanup_status,
        next_actions=next_actions,
        message=message,
    )
    _save_report_to_dir(report, report_dir)
    return report


def _save_report_to_dir(report: RehearsalReport, report_dir: Path | None) -> None:
    if report_dir is None:
        return
    report_dir.mkdir(parents=True, exist_ok=True)
    fname = (
        f"migration_rehearsal_{report.source_env}_{report.source_version}"
        f"_to_{report.target_version}.json"
    )
    report_file = report_dir / fname
    report_file.write_text(json.dumps(report.to_dict(), indent=2))
    if report.log_path is None:
        report.log_path = str(report_file)


def _build_next_actions(
    status: str,
    failed_modules: list[str],
    warnings: list[str],
    target_version: str,
) -> list[str]:
    actions: list[str] = []
    if status == "success":
        actions.append(
            "Review the full migration report for warnings before scheduling the production upgrade."
        )
        actions.append(
            f"Schedule a maintenance window for the production upgrade to {target_version}."
        )
        actions.append(
            "Take a fresh production backup immediately before the production upgrade."
        )
    else:
        if failed_modules:
            failed_str = ", ".join(failed_modules[:5])
            if len(failed_modules) > 5:
                failed_str += f" (and {len(failed_modules) - 5} more)"
            actions.append(f"Investigate failed modules: {failed_str}.")
            actions.append("Check OpenUpgrade migration scripts for each failed module.")
        if warnings:
            actions.append("Address scan warnings and re-run: odooctl migrate rehearse.")
        actions.append("Fix the issues above, then re-run: odooctl migrate rehearse.")
    return actions
