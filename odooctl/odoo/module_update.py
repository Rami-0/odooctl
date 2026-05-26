from __future__ import annotations
import os

from odooctl.adapters.docker_compose import DockerComposeAdapter
from odooctl.utils.shell import join_csv, run


def build_update_modules_args(
    db_name: str,
    modules: list[str],
    *,
    db_host: str | None = None,
    db_user: str | None = None,
    db_password_env: str | None = None,
    config_path: str | None = None,
) -> list[str]:
    args = ["odoo", "-d", db_name, "-u", join_csv(modules), "--stop-after-init"]
    if config_path:
        args.extend(["-c", config_path])
    if db_host:
        args.extend(["--db_host", db_host])
    if db_user:
        args.extend(["--db_user", db_user])
    if db_password_env:
        value = os.getenv(db_password_env)
        if not value:
            raise RuntimeError(f"Missing required environment variable: {db_password_env}")
        args.extend(["--db_password", value])
    return args


def update_modules_local(db_name: str, modules: list[str]) -> None:
    if not modules:
        return
    run(build_update_modules_args(db_name, modules), stream=True)


def update_modules_compose(
    compose: DockerComposeAdapter,
    service: str,
    db_name: str,
    modules: list[str],
    *,
    db_host: str | None = None,
    db_user: str | None = None,
    db_password_env: str | None = None,
    config_path: str | None = None,
) -> None:
    if not modules:
        return
    compose.exec(
        service,
        build_update_modules_args(
            db_name,
            modules,
            db_host=db_host,
            db_user=db_user,
            db_password_env=db_password_env,
            config_path=config_path,
        ),
        stream=True,
    )
