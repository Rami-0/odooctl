from __future__ import annotations

from pathlib import Path
from typing import Protocol

from odooctl.adapters.postgres import PostgresAdapter
from odooctl.context import ProjectContext
from odooctl.utils.shell import run


class DbAdapter(Protocol):
    def ping(self, db_name: str) -> None: ...
    def dump(self, db_name: str, output: str | Path) -> None: ...
    def restore(self, db_name: str, dump_path: str | Path) -> None: ...
    def drop_create(self, db_name: str) -> None: ...
    def psql_file(self, db_name: str, sql_file: str | Path) -> None: ...
    def psql(self, db_name: str, sql: str) -> None: ...


class HostPostgresAdapter(PostgresAdapter):
    """Host PostgreSQL adapter kept for backward-compatible host execution."""


class DockerPostgresAdapter:
    """PostgreSQL adapter that executes client tools inside the compose DB service."""

    def __init__(self, ctx: ProjectContext):
        self.ctx = ctx
        self.config = ctx.config.postgres

    @property
    def project_dir(self) -> str:
        return str(self.ctx.root)

    def _cmd(self, *args: str) -> list[str]:
        return [
            "docker",
            "compose",
            "-f",
            str(self.ctx.compose_file),
            "exec",
            "-T",
            self.config.service,
            *args,
        ]

    def _password_env(self) -> dict[str, str]:
        return {"PGPASSWORD": self.config.service_password()}

    def base_args(self) -> list[str]:
        return ["-h", self.config.internal_host, "-U", self.config.service_user]

    def ping(self, db_name: str) -> None:
        run(self._cmd("pg_isready", "-d", db_name, *self.base_args()), cwd=self.project_dir, env=self._password_env())

    def dump(self, db_name: str, output: str | Path) -> None:
        from odooctl.utils.shell import run_capture_bytes

        run_capture_bytes(
            self._cmd("pg_dump", *self.base_args(), "-Fc", "-d", db_name),
            cwd=self.project_dir,
            env=self._password_env(),
            stdout_path=output,
        )

    def restore(self, db_name: str, dump_path: str | Path) -> None:
        from odooctl.utils.shell import run_pipe_stdin

        self.drop_create(db_name)
        run_pipe_stdin(
            self._cmd("pg_restore", *self.base_args(), "-d", db_name),
            cwd=self.project_dir,
            env=self._password_env(),
            stdin_path=dump_path,
        )

    def drop_create(self, db_name: str) -> None:
        run(self._cmd("dropdb", *self.base_args(), db_name, "--if-exists"), cwd=self.project_dir, env=self._password_env(), stream=True)
        run(self._cmd("createdb", *self.base_args(), db_name), cwd=self.project_dir, env=self._password_env(), stream=True)

    def psql_file(self, db_name: str, sql_file: str | Path) -> None:
        run(self._cmd("psql", *self.base_args(), "-d", db_name, "-v", "ON_ERROR_STOP=1", "-f", str(sql_file)), cwd=self.project_dir, env=self._password_env(), stream=True)

    def psql(self, db_name: str, sql: str) -> None:
        run(self._cmd("psql", *self.base_args(), "-d", db_name, "-v", "ON_ERROR_STOP=1", "-c", sql), cwd=self.project_dir, env=self._password_env(), stream=True)

    def clone_db_in_container(self, src: str, dst: str) -> None:
        self.drop_create(dst)
        script = f"pg_dump -Fc -h {self.config.internal_host} -U {self.config.service_user} -d {src} | pg_restore -h {self.config.internal_host} -U {self.config.service_user} -d {dst}"
        run(self._cmd("sh", "-lc", script), cwd=self.project_dir, env=self._password_env(), stream=True)


def make_db_adapter(ctx: ProjectContext) -> DbAdapter:
    if ctx.config.runtime.execution_mode == "host":
        return HostPostgresAdapter(ctx.config.postgres)
    return DockerPostgresAdapter(ctx)
