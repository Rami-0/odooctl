from __future__ import annotations
from pathlib import Path
from typing import Protocol
from odooctl.config import OdooCtlConfig, EnvironmentConfig
from odooctl.adapters.reverse_proxy import public_url


class PsqlAdapter(Protocol):
    def psql(self, db_name: str, sql: str) -> None: ...
    def psql_file(self, db_name: str, sql_file: str | Path) -> None: ...


def guarded_update(table: str, sql: str) -> str:
    escaped = sql.replace("'", "''")
    return (
        "DO $$ BEGIN "
        f"IF to_regclass('public.{table}') IS NOT NULL THEN "
        f"EXECUTE '{escaped}'; "
        "END IF; END $$;"
    )


def guarded_column_update(table: str, column: str, sql: str) -> str:
    escaped = sql.replace("'", "''")
    return (
        "DO $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM information_schema.columns "
        f"WHERE table_schema = 'public' AND table_name = '{table}' AND column_name = '{column}') THEN "
        f"EXECUTE '{escaped}'; "
        "END IF; END $$;"
    )


def baseline_sql(env: EnvironmentConfig, config: OdooCtlConfig) -> list[str]:
    """Statements applied by every profile, including ``minimal``.

    Anything here is considered mandatory for a safe staging clone: no outbound
    mail, no crons, no live payment calls, and a rewritten (frozen) base URL.
    """
    stmts: list[str] = []
    if config.sanitization.disable_mail_servers:
        stmts.append(guarded_update("ir_mail_server", "UPDATE ir_mail_server SET active = false;"))
    if config.sanitization.disable_fetchmail:
        stmts.append(guarded_update("fetchmail_server", "UPDATE fetchmail_server SET active = false;"))
    if config.sanitization.disable_crons:
        stmts.append(guarded_update("ir_cron", "UPDATE ir_cron SET active = false WHERE active = true;"))
    if config.sanitization.disable_payment_providers:
        # Modern table (Odoo >= 16).
        stmts.append(guarded_update("payment_provider", "UPDATE payment_provider SET state = 'disabled' WHERE state != 'disabled';"))
        # Legacy table (Odoo < 16); guarded so it no-ops on modern databases.
        stmts.append(guarded_update("payment_acquirer", "UPDATE payment_acquirer SET state = 'disabled' WHERE state != 'disabled';"))
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
        # Freeze the base URL so Odoo does not rewrite it back to the
        # production URL on the next admin login.
        stmts.append("UPDATE ir_config_parameter SET value = 'True' WHERE key = 'web.base.url.freeze';")
        stmts.append(
            "INSERT INTO ir_config_parameter (key, value) "
            "SELECT 'web.base.url.freeze', 'True' "
            "WHERE NOT EXISTS (SELECT 1 FROM ir_config_parameter WHERE key = 'web.base.url.freeze');"
        )
    return stmts


def aggressive_sql(config: OdooCtlConfig) -> list[str]:
    """Statements applied by ``normal`` and ``strict`` profiles (not ``minimal``).

    These remove credential material carried over from production: OAuth
    providers, IAP/SMS tokens, and WebAuthn passkeys.
    """
    stmts: list[str] = [
        # OAuth providers: disable and drop client secrets so staging cannot
        # authenticate against production identity providers.
        guarded_column_update("auth_oauth_provider", "enabled", "UPDATE auth_oauth_provider SET enabled = false;"),
        guarded_column_update("auth_oauth_provider", "active", "UPDATE auth_oauth_provider SET active = false;"),
        guarded_column_update("auth_oauth_provider", "client_secret", "UPDATE auth_oauth_provider SET client_secret = NULL;"),
        # IAP (SMS, snailmail, partner autocomplete, ...) account tokens.
        guarded_column_update("iap_account", "account_token", "UPDATE iap_account SET account_token = NULL;"),
        # Odoo 19 WebAuthn passkeys (auth_passkey module): a cloned production
        # database must not carry passkeys that unlock staging with production
        # credentials. Guarded so it no-ops on older versions.
        guarded_update("auth_passkey_key", "DELETE FROM auth_passkey_key;"),
    ]
    return stmts


def default_sql(env: EnvironmentConfig, config: OdooCtlConfig) -> list[str]:
    return baseline_sql(env, config) + aggressive_sql(config)


def profile_sql(profile: str, env: EnvironmentConfig, config: OdooCtlConfig) -> list[str]:
    if profile not in {"strict", "normal", "minimal"}:
        raise ValueError(f"Unknown sanitization profile: {profile}")
    if profile == "minimal":
        # Crons stay disabled even under minimal: a cloned production database
        # with live crons can send mail, hit webhooks, and charge cards.
        return baseline_sql(env, config)
    stmts = default_sql(env, config)
    if profile == "strict":
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
