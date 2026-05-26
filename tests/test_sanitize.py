from pathlib import Path

import pytest

from odooctl.config import example_config, load_config
from odooctl.odoo.sanitize import default_sql, profile_sql, sanitize_database


class FakePostgres:
    def psql(self, db_name, sql):
        pass

    def psql_file(self, db_name, sql_file):
        pass


def test_default_sanitization_disables_dangerous_integrations(tmp_path: Path):
    path = tmp_path / "odooctl.yml"
    path.write_text(example_config())
    cfg = load_config(path)
    sql = "\n".join(default_sql(cfg.env("staging"), cfg))
    assert "UPDATE ir_mail_server SET active = false" in sql
    assert "UPDATE fetchmail_server SET active = false" in sql
    assert "UPDATE ir_cron SET active = false" in sql
    assert "payment_provider" in sql
    assert "queue_job" in sql
    assert "base_automation" in sql
    assert "mail_mail" in sql
    assert "https://staging.odoo.example.com" in sql


def test_missing_configured_sanitization_sql_fails(tmp_path: Path, monkeypatch):
    path = tmp_path / "odooctl.yml"
    path.write_text(example_config())
    cfg = load_config(path)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        sanitize_database(FakePostgres(), "odoo_staging", cfg.env("staging"), cfg)


def test_sanitization_profiles_are_explicit_and_distinct(tmp_path: Path):
    path = tmp_path / "odooctl.yml"
    path.write_text(example_config())
    cfg = load_config(path)
    env = cfg.env("staging")

    strict_sql = "\n".join(profile_sql("strict", env, cfg))
    normal_sql = "\n".join(profile_sql("normal", env, cfg))
    minimal_sql = "\n".join(profile_sql("minimal", env, cfg))

    assert "UPDATE ir_mail_server SET active = false" in strict_sql
    assert "UPDATE ir_cron SET active = false" in strict_sql
    assert "UPDATE ir_mail_server SET active = false" in normal_sql
    assert "UPDATE ir_cron SET active = false" in normal_sql
    assert "UPDATE ir_mail_server SET active = false" in minimal_sql
    assert "UPDATE ir_cron SET active = false" not in minimal_sql


def test_default_sanitization_scrubs_webhooks_and_environment_secrets(tmp_path: Path):
    path = tmp_path / "odooctl.yml"
    path.write_text(example_config())
    cfg = load_config(path)

    sql = "\n".join(default_sql(cfg.env("staging"), cfg))

    assert "webhook" in sql
    assert "callback" in sql
    assert "api_key" in sql
    assert "secret" in sql
    assert "token" in sql
