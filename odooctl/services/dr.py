"""Disaster recovery drill service."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TYPE_CHECKING

from odooctl.services.restore import resolve_backup_dir, validate_backup_dir

if TYPE_CHECKING:
    pass


@dataclass
class DrDrillResult:
    status: str  # "success" | "failed"
    environment: str
    backup_id: str | None
    message: str | None = None


def run_dr_drill(
    *,
    environment: str,
    backups_root: str | Path,
    db_adapter,
    fs_adapter,
    healthcheck_fn: Callable[[str], bool],
    is_protected_fn: Callable[[str], bool] | None = None,
    throwaway_db_suffix: str = "_dr_drill",
    healthcheck_url: str = "http://localhost:8069/web/login",
) -> DrDrillResult:
    """Run a DR drill for *environment* (the SOURCE whose latest backup is drilled).

    The environment may be protected (e.g. production). Steps:
    1. Resolve the latest backup for *environment*.
    2. Validate backup checksums.
    3. Restore DB into a throwaway DB (never the live DB — guarded).
    4. Run healthcheck_fn.
    5. Always drop the throwaway DB (cleanup).

    Safety guard: *throwaway_db_suffix* must produce a name that differs from
    the manifest's live DB name, preventing accidental restoration into the
    live database.
    """
    backups_root = Path(backups_root)
    backup_dir = resolve_backup_dir(environment, "latest", backups_root)
    manifest = validate_backup_dir(backup_dir)

    source_db_name = manifest.get("db_name") or f"{environment}_db"
    throwaway_db = f"{source_db_name}{throwaway_db_suffix}"

    if throwaway_db == source_db_name:
        raise RuntimeError(
            f"Throwaway DB name {throwaway_db!r} must differ from the live DB "
            f"{source_db_name!r}. Use a non-empty throwaway_db_suffix to prevent "
            "accidentally targeting the live database."
        )

    backup_id = backup_dir.name

    status = "failed"
    message = None
    try:
        db_adapter.restore(throwaway_db, backup_dir / "db.dump")
        ok = healthcheck_fn(healthcheck_url)
        if ok:
            status = "success"
        else:
            message = "Healthcheck returned False after restore."
    except Exception as exc:
        message = str(exc)
        status = "failed"
    finally:
        try:
            db_adapter.drop(throwaway_db)
        except Exception:
            pass

    return DrDrillResult(
        status=status,
        environment=environment,
        backup_id=backup_id,
        message=message,
    )
