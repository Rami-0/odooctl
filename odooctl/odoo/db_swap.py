from __future__ import annotations

from typing import Callable, Protocol


class SwapPsqlAdapter(Protocol):
    def psql(self, db_name: str, sql: str) -> None: ...


def quote_identifier(name: str) -> str:
    """Return a PostgreSQL quoted identifier for a database name."""
    if "\x00" in name:
        raise ValueError("database name cannot contain NUL bytes")
    return '"' + name.replace('"', '""') + '"'


def quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def terminate_connections(pg: SwapPsqlAdapter, db_name: str, *, maintenance_db: str = "postgres") -> None:
    pg.psql(
        maintenance_db,
        "SELECT pg_terminate_backend(pid) "
        "FROM pg_stat_activity "
        f"WHERE datname = {quote_literal(db_name)} AND pid <> pg_backend_pid();",
    )


def drop_database(pg: SwapPsqlAdapter, db_name: str, *, maintenance_db: str = "postgres") -> None:
    pg.psql(maintenance_db, f"DROP DATABASE IF EXISTS {quote_identifier(db_name)};")


def rename_database(pg: SwapPsqlAdapter, old_name: str, new_name: str, *, maintenance_db: str = "postgres") -> None:
    pg.psql(maintenance_db, f"ALTER DATABASE {quote_identifier(old_name)} RENAME TO {quote_identifier(new_name)};")


def swap_temp_database(
    pg: SwapPsqlAdapter,
    *,
    temp_db: str,
    target_db: str,
    target_env_name: str,
    is_protected_fn: Callable[[str], bool] | None = None,
    maintenance_db: str = "postgres",
) -> None:
    """Promote a prepared temp DB into the target DB name, crash/failure-safe.

    ``is_protected_fn`` (typically ``OdooCtlConfig.is_protected``) guards
    against accidental promotion over a protected environment such as
    production; callers that omit it must enforce that policy themselves
    before invoking this function. Callers are expected to restore and
    sanitize ``temp_db`` before invoking this function.

    When the adapter exposes ``database_exists`` (the real Postgres adapters),
    the swap moves the live target aside, promotes the temp DB, and only drops
    the aside copy once the new DB is live — restoring the original if the
    promotion rename fails. The target name is therefore never left without a
    database (Opus M3 / codex re-scan #3). Adapters without ``database_exists``
    fall back to the drop-then-rename path.
    """
    if is_protected_fn is not None and is_protected_fn(target_env_name):
        raise RuntimeError(
            f"Refusing to swap a temporary database into protected environment '{target_env_name}'"
        )
    if temp_db == target_db:
        raise RuntimeError("Temporary database name must differ from target database name")

    exists_fn = getattr(pg, "database_exists", None)
    if not callable(exists_fn):
        # Legacy path for adapters that cannot query database existence. On a
        # crash between drop and rename the target name is briefly absent, but
        # the data survives under ``temp_db`` and is recoverable.
        terminate_connections(pg, target_db, maintenance_db=maintenance_db)
        drop_database(pg, target_db, maintenance_db=maintenance_db)
        rename_database(pg, temp_db, target_db, maintenance_db=maintenance_db)
        return

    aside_db = f"{target_db}__old_swap"
    if exists_fn(aside_db):
        terminate_connections(pg, aside_db, maintenance_db=maintenance_db)
        drop_database(pg, aside_db, maintenance_db=maintenance_db)

    target_existed = bool(exists_fn(target_db))
    if target_existed:
        terminate_connections(pg, target_db, maintenance_db=maintenance_db)
        rename_database(pg, target_db, aside_db, maintenance_db=maintenance_db)
    try:
        rename_database(pg, temp_db, target_db, maintenance_db=maintenance_db)
    except Exception:
        # Promotion failed: restore the original so the target is never absent.
        if target_existed and exists_fn(aside_db):
            rename_database(pg, aside_db, target_db, maintenance_db=maintenance_db)
        raise
    if target_existed and exists_fn(aside_db):
        terminate_connections(pg, aside_db, maintenance_db=maintenance_db)
        drop_database(pg, aside_db, maintenance_db=maintenance_db)
