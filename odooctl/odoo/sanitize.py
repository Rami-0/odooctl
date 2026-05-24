from __future__ import annotations
from pathlib import Path
from odooctl.config import OdooCtlConfig, EnvironmentConfig
from odooctl.adapters.postgres import PostgresAdapter
from odooctl.adapters.reverse_proxy import public_url


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
    if config.sanitization.rewrite_base_url:
        url = public_url(env.domain).replace("'", "''")
        stmts.append("UPDATE ir_config_parameter SET value = '%s' WHERE key = 'web.base.url';" % url)
    return stmts


def sanitize_database(pg: PostgresAdapter, db_name: str, env: EnvironmentConfig, config: OdooCtlConfig) -> None:
    for sql in default_sql(env, config):
        pg.psql(db_name, sql)
    for file_name in config.sanitization.sql_files:
        path = Path(file_name)
        if not path.exists():
            raise FileNotFoundError(f"Configured sanitization SQL file does not exist: {file_name}")
        pg.psql_file(db_name, path)
