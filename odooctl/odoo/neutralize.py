"""Run Odoo's own database neutralization (``odoo-bin neutralize``).

Odoo >= 16 ships a ``neutralize`` command that executes per-module
``neutralize.sql`` scripts maintained upstream. odooctl runs it as the primary
sanitization mechanism where available; the hand-rolled SQL in
``odooctl.odoo.sanitize`` then covers what upstream does not (pre-16 databases,
third-party modules, ``ir_config_parameter`` secrets, base URL rewrite).
"""
from __future__ import annotations

from typing import Callable

from odooctl.adapters.docker_compose import DockerComposeAdapter
from odooctl.odoo.module_update import resolve_password_env

NEUTRALIZE_MIN_MAJOR = 16

NeutralizeRunner = Callable[[str], None]


def supports_neutralize(odoo_version: str) -> bool:
    """True when the given Odoo version ships ``odoo-bin neutralize``."""
    major = odoo_version.split(".", 1)[0]
    try:
        return int(major) >= NEUTRALIZE_MIN_MAJOR
    except ValueError:
        return False


def build_neutralize_args(
    db_name: str,
    *,
    db_host: str | None = None,
    db_user: str | None = None,
    config_path: str | None = None,
) -> list[str]:
    args = ["odoo", "neutralize", "-d", db_name]
    if config_path:
        args.extend(["-c", config_path])
    if db_host:
        args.extend(["--db_host", db_host])
    if db_user:
        args.extend(["--db_user", db_user])
    return args


def neutralize_compose(
    compose: DockerComposeAdapter,
    service: str,
    db_name: str,
    *,
    db_host: str | None = None,
    db_user: str | None = None,
    db_password_env: str | None = None,
    config_path: str | None = None,
) -> None:
    extra_env = resolve_password_env(db_password_env)
    compose.exec(
        service,
        build_neutralize_args(
            db_name,
            db_host=db_host,
            db_user=db_user,
            config_path=config_path,
        ),
        stream=True,
        extra_env=extra_env,
    )


def compose_neutralizer(
    compose: DockerComposeAdapter,
    service: str,
    *,
    db_host: str | None = None,
    db_user: str | None = None,
    db_password_env: str | None = None,
    config_path: str | None = None,
) -> NeutralizeRunner:
    """Bind compose/service/connection details into a ``db_name -> None`` runner."""

    def _run(db_name: str) -> None:
        neutralize_compose(
            compose,
            service,
            db_name,
            db_host=db_host,
            db_user=db_user,
            db_password_env=db_password_env,
            config_path=config_path,
        )

    return _run
