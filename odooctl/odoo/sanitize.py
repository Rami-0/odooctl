from __future__ import annotations
from pathlib import Path
from typing import Protocol
from odooctl.config import OdooCtlConfig, EnvironmentConfig
from odooctl.adapters.reverse_proxy import public_url


class PsqlAdapter(Protocol):
    def psql(self, db_name: str, sql: str) -> None: ...
    def psql_file(self, db_name: str, sql_file: str | Path) -> None: ...


def default_sql(env: EnvironmentConfig, config: OdooCtlConfig) -> list[str]:
    stmts: list[str] = []
    if config.sanitization.disable_mail_servers:
        stmts.append("UPDATE ir_mail_server SET active = false;")
    if config.sanitization.disable_fetchmail:
        stmts.append("UPDATE fetchmail_server SET active = false;")
    if config.sanitization.disable_crons:
        stmts.append("UPDATE ir_cron SET active = false WHERE active = true;")
    if config.sanitization.disable_payment_providers:
        stmts.append("UPDATE payment_provider SET state = 'disabled' WHERE state != 'disabled';")
    if config.sanitization.disable_queue_jobs:
        stmts.append(
            "DO $$ BEGIN "
            "IF to_regclass('public.queue_job') IS NOT NULL THEN "
            "UPDATE queue_job SET state = 'cancelled' WHERE state NOT IN ('done', 'cancelled'); "
            "END IF; END $$;"
        )
        stmts.append(
            "DO $$ BEGIN "
            "IF to_regclass('public.base_automation') IS NOT NULL THEN "
            "UPDATE base_automation SET active = false WHERE active = true; "
            "END IF; END $$;"
        )
    if config.sanitization.purge_mail_queue:
        stmts.append(
            "DO $$ BEGIN "
            "IF to_regclass('public.mail_mail') IS NOT NULL THEN "
            "DELETE FROM mail_mail WHERE state != 'sent'; "
            "END IF; END $$;"
        )
    stmts.append(
        "UPDATE ir_config_parameter SET value = '' "
        "WHERE key ILIKE '%webhook%' OR key ILIKE '%callback%' OR key ILIKE '%endpoint_url%';"
    )
    stmts.append(
        "UPDATE ir_config_parameter SET value = '' "
        "WHERE key ILIKE '%api_key%' OR key ILIKE '%secret%' OR key ILIKE '%token%' OR key ILIKE '%password%';"
    )
    if config.sanitization.rewrite_base_url:
        scheme = config.healthcheck.scheme or env.scheme
        url = public_url(env.domain, scheme=scheme, port=env.port).replace("'", "''")
        stmts.append("UPDATE ir_config_parameter SET value = '%s' WHERE key = 'web.base.url';" % url)
    return stmts


def profile_sql(profile: str, env: EnvironmentConfig, config: OdooCtlConfig) -> list[str]:
    if profile not in {"strict", "normal", "minimal"}:
        raise ValueError(f"Unknown sanitization profile: {profile}")
    stmts = default_sql(env, config)
    if profile == "minimal":
        stmts = [sql for sql in stmts if "ir_cron" not in sql]
    elif profile == "strict":
        extra = ["UPDATE ir_config_parameter SET value = '' WHERE key LIKE 'auth_%';"]
        stmts = extra + stmts
    return stmts


def sanitize_database(
    pg: PsqlAdapter,
    db_name: str,
    env: EnvironmentConfig,
    config: OdooCtlConfig,
    profile: str = "normal",
    *,
    sql_files: list[Path] | None = None,
) -> None:
    for sql in profile_sql(profile, env, config):
        pg.psql(db_name, sql)
    paths = sql_files if sql_files is not None else [Path(file_name) for file_name in config.sanitization.sql_files]
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Configured sanitization SQL file does not exist: {path}")
        pg.psql_file(db_name, path)
