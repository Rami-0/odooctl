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
    """Atomically promote a prepared temp DB into the target DB name.

    ``is_protected_fn`` (typically ``OdooCtlConfig.is_protected``) guards
    against accidental promotion over a protected environment such as
    production; callers that omit it must enforce that policy themselves
    before invoking this function. Callers are expected to restore and
    sanitize ``temp_db`` before invoking this function.
    """
    if is_protected_fn is not None and is_protected_fn(target_env_name):
        raise RuntimeError(
            f"Refusing to swap a temporary database into protected environment '{target_env_name}'"
        )
    if temp_db == target_db:
        raise RuntimeError("Temporary database name must differ from target database name")
    terminate_connections(pg, target_db, maintenance_db=maintenance_db)
    drop_database(pg, target_db, maintenance_db=maintenance_db)
    rename_database(pg, temp_db, target_db, maintenance_db=maintenance_db)
