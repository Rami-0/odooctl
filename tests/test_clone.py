from __future__ import annotations

from pathlib import Path

import pytest

from odooctl.commands.clone import execute


def test_clone_orchestrates_dump_restore_sanitize_update_and_healthcheck(tmp_path: Path, monkeypatch):
    config = tmp_path / "odooctl.yml"
    config.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\npostgres:\n  host: localhost\n  port: 5432\n  user: odoo\n  password_env: ODOO_DB_PASSWORD\nbackups:\n  local_path: backups\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\nodoo:\n  image: registry/odoo:latest\n  service: odoo\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /srv/filestore/prod\n    update_modules: [sale, stock]\n    sanitize: true\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /srv/filestore/staging\n    clone_from: production\n    update_modules: [sale]\n    sanitize: true\n"""
    )
    (tmp_path / "docker-compose.yml").touch()

    events: list[tuple[str, tuple[object, ...]]] = []

    class DummyPostgres:
        def __init__(self, config):
            events.append(("postgres_init", (config.host, config.port, config.user)))

        def dump(self, db_name, output):
            events.append(("dump", (db_name, Path(output).name)))

        def restore(self, db_name, dump_path):
            events.append(("restore", (db_name, Path(dump_path).name)))

        def psql(self, db_name, sql):
            events.append(("psql", (db_name, sql)))

    class DummyFilestore:
        def copy(self, source, target):
            events.append(("copy", (source, target)))

    class DummyCompose:
        def __init__(self, compose_file):
            events.append(("compose_init", (compose_file,)))

        def exec(self, service, args, *, stream=True):
            events.append(("exec", (service, tuple(args), stream)))

        def restart(self, service):
            events.append(("restart", (service,)))

        def ps(self):
            events.append(("ps", ()))
            return "odoo running"

    monkeypatch.setattr("odooctl.commands.clone.PostgresAdapter", DummyPostgres)
    monkeypatch.setattr("odooctl.commands.clone.FilestoreAdapter", DummyFilestore)
    monkeypatch.setattr("odooctl.commands.clone.DockerComposeAdapter", DummyCompose)
    monkeypatch.setattr("odooctl.commands.clone.update_modules_compose", lambda compose, service, db_name, modules: events.append(("update", (service, db_name, tuple(modules)))))
    monkeypatch.setattr("odooctl.commands.clone.check_url", lambda url, **kwargs: events.append(("healthcheck", (url, kwargs["timeout"], kwargs["retries"], kwargs["interval"])) ))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")

    url = execute("production", "staging", True, str(config))

    assert url == "https://staging.example.com"
    assert events[0] == ("postgres_init", ("localhost", 5432, "odoo"))
    assert events[1][0] == "dump" and events[1][1][0] == "odoo_prod" and str(events[1][1][1]).endswith(".dump")
    assert events[2][0] == "restore" and events[2][1][0] == "odoo_staging" and str(events[2][1][1]).endswith(".dump")
    assert events[3] == ("copy", ("/srv/filestore/prod", "/srv/filestore/staging"))
    assert events[4] == ("psql", ("odoo_staging", "UPDATE ir_mail_server SET active = false;"))
    assert events[5] == ("psql", ("odoo_staging", "UPDATE fetchmail_server SET active = false;"))
    assert events[6] == ("psql", ("odoo_staging", "UPDATE ir_cron SET active = false WHERE active = true;"))
    assert events[7] == ("psql", ("odoo_staging", "UPDATE payment_provider SET state = 'disabled' WHERE state != 'disabled';"))
    psql_sql = [str(args[1]) for event, args in events if event == "psql" and args[0] == "odoo_staging"]
    assert "UPDATE ir_config_parameter SET value = 'https://staging.example.com' WHERE key = 'web.base.url';" in psql_sql
    assert any("webhook" in sql and "callback" in sql for sql in psql_sql)
    assert any("api_key" in sql and "secret" in sql and "token" in sql for sql in psql_sql)
    assert ("compose_init", ("docker-compose.yml",)) in events
    assert ("update", ("odoo", "odoo_staging", ("sale",))) in events
    assert events[-3] == ("restart", ("odoo",))
    assert events[-2] == ("ps", ())
    assert events[-1] == ("healthcheck", ("https://staging.example.com/web/health", 10, 3, 1))


def test_clone_supports_explicit_sanitization_profiles(tmp_path: Path, monkeypatch):
    config = tmp_path / "odooctl.yml"
    config.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\npostgres:\n  host: localhost\n  port: 5432\n  user: odoo\n  password_env: ODOO_DB_PASSWORD\nbackups:\n  local_path: backups\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\nodoo:\n  image: registry/odoo:latest\n  service: odoo\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /srv/filestore/prod\n    update_modules: [sale, stock]\n    sanitize: true\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /srv/filestore/staging\n    clone_from: production\n    update_modules: [sale]\n    sanitize: true\n"""
    )
    (tmp_path / "docker-compose.yml").touch()

    events: list[tuple[str, tuple[object, ...]]] = []

    class DummyPostgres:
        def __init__(self, config):
            pass

        def dump(self, db_name, output):
            pass

        def restore(self, db_name, dump_path):
            pass

        def psql(self, db_name, sql):
            events.append(("psql", (db_name, sql)))

    class DummyFilestore:
        def copy(self, source, target):
            pass

    class DummyCompose:
        def __init__(self, compose_file):
            pass

        def exec(self, service, args, *, stream=True):
            pass

        def restart(self, service):
            pass

        def ps(self):
            return "odoo running"

    monkeypatch.setattr("odooctl.commands.clone.PostgresAdapter", DummyPostgres)
    monkeypatch.setattr("odooctl.commands.clone.FilestoreAdapter", DummyFilestore)
    monkeypatch.setattr("odooctl.commands.clone.DockerComposeAdapter", DummyCompose)
    monkeypatch.setattr("odooctl.commands.clone.update_modules_compose", lambda *args, **kwargs: None)
    monkeypatch.setattr("odooctl.commands.clone.check_url", lambda *args, **kwargs: None)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")

    execute("production", "staging", True, str(config), sanitization_profile="minimal")

    assert any("UPDATE ir_mail_server SET active = false" in sql for _, (db, sql) in events if db == "odoo_staging")
    assert not any("UPDATE ir_cron SET active = false" in sql for _, (db, sql) in events if db == "odoo_staging")


def test_clone_applies_configured_sanitization_sql_files(tmp_path: Path, monkeypatch):
    config = tmp_path / "odooctl.yml"
    config.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\npostgres:\n  host: localhost\n  port: 5432\n  user: odoo\n  password_env: ODOO_DB_PASSWORD\nbackups:\n  local_path: backups\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\nodoo:\n  image: registry/odoo:latest\n  service: odoo\nsanitization:\n  sql_files: [.sanitize/extra.sql]\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /srv/filestore/prod\n    update_modules: [sale, stock]\n    sanitize: true\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /srv/filestore/staging\n    clone_from: production\n    update_modules: [sale]\n    sanitize: true\n"""
    )
    (tmp_path / "docker-compose.yml").touch()
    (tmp_path / ".sanitize").mkdir()
    extra_sql = tmp_path / ".sanitize" / "extra.sql"
    extra_sql.write_text("UPDATE res_partner SET email = NULL;\n")
    events: list[tuple[str, tuple[object, ...]]] = []

    class DummyPostgres:
        def __init__(self, config):
            pass

        def dump(self, db_name, output):
            pass

        def restore(self, db_name, dump_path):
            pass

        def psql(self, db_name, sql):
            events.append(("psql", (db_name, sql)))

        def psql_file(self, db_name, path):
            events.append(("psql_file", (db_name, Path(path))))

    class DummyFilestore:
        def copy(self, source, target):
            pass

    class DummyCompose:
        def __init__(self, compose_file):
            pass

        def exec(self, service, args, *, stream=True):
            pass

        def restart(self, service):
            pass

        def ps(self):
            return "odoo running"

    monkeypatch.setattr("odooctl.commands.clone.PostgresAdapter", DummyPostgres)
    monkeypatch.setattr("odooctl.commands.clone.FilestoreAdapter", DummyFilestore)
    monkeypatch.setattr("odooctl.commands.clone.DockerComposeAdapter", DummyCompose)
    monkeypatch.setattr("odooctl.commands.clone.update_modules_compose", lambda *args, **kwargs: None)
    monkeypatch.setattr("odooctl.commands.clone.check_url", lambda *args, **kwargs: None)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")

    execute("production", "staging", True, str(config))

    assert ("psql_file", ("odoo_staging", extra_sql)) in events
    assert [event for event, _ in events].index("psql_file") > [event for event, _ in events].index("psql")


def test_clone_fails_when_configured_sanitization_sql_file_is_missing(tmp_path: Path, monkeypatch):
    config = tmp_path / "odooctl.yml"
    config.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\npostgres:\n  host: localhost\n  port: 5432\n  user: odoo\n  password_env: ODOO_DB_PASSWORD\nbackups:\n  local_path: backups\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\nodoo:\n  image: registry/odoo:latest\n  service: odoo\nsanitization:\n  sql_files: [.sanitize/missing.sql]\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /srv/filestore/prod\n    sanitize: true\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /srv/filestore/staging\n    clone_from: production\n    sanitize: true\n"""
    )
    (tmp_path / "docker-compose.yml").touch()

    class DummyPostgres:
        def __init__(self, config):
            pass

        def dump(self, db_name, output):
            pass

        def restore(self, db_name, dump_path):
            pass

        def psql(self, db_name, sql):
            pass

    class DummyFilestore:
        def copy(self, source, target):
            pass

    monkeypatch.setattr("odooctl.commands.clone.PostgresAdapter", DummyPostgres)
    monkeypatch.setattr("odooctl.commands.clone.FilestoreAdapter", DummyFilestore)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")

    with pytest.raises(FileNotFoundError, match="Configured sanitization SQL file does not exist"):
        execute("production", "staging", True, str(config))


def test_clone_verification_fails_when_target_service_is_not_running(tmp_path: Path, monkeypatch):
    config = tmp_path / "odooctl.yml"
    config.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\npostgres:\n  host: localhost\n  port: 5432\n  user: odoo\n  password_env: ODOO_DB_PASSWORD\nbackups:\n  local_path: backups\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\nodoo:\n  image: registry/odoo:latest\n  service: odoo\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /srv/filestore/prod\n    update_modules: [sale, stock]\n    sanitize: true\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /srv/filestore/staging\n    clone_from: production\n    update_modules: [sale]\n    sanitize: true\n"""
    )
    (tmp_path / "docker-compose.yml").touch()

    class DummyPostgres:
        def __init__(self, config):
            pass

        def dump(self, db_name, output):
            pass

        def restore(self, db_name, dump_path):
            pass

        def psql(self, db_name, sql):
            pass

    class DummyFilestore:
        def copy(self, source, target):
            pass

    class DummyCompose:
        def __init__(self, compose_file):
            pass

        def restart(self, service):
            pass

        def ps(self):
            return "postgres running"

    monkeypatch.setattr("odooctl.commands.clone.PostgresAdapter", DummyPostgres)
    monkeypatch.setattr("odooctl.commands.clone.FilestoreAdapter", DummyFilestore)
    monkeypatch.setattr("odooctl.commands.clone.DockerComposeAdapter", DummyCompose)
    monkeypatch.setattr("odooctl.commands.clone.update_modules_compose", lambda *args, **kwargs: None)
    monkeypatch.setattr("odooctl.commands.clone.check_url", lambda *args, **kwargs: None)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")

    with pytest.raises(RuntimeError, match="Target service is not running"):
        execute("production", "staging", True, str(config))


def test_clone_preview_is_readable_and_side_effect_free(tmp_path: Path, monkeypatch, capsys):
    config = tmp_path / "odooctl.yml"
    config.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\npostgres:\n  host: localhost\n  port: 5432\n  user: odoo\n  password_env: ODOO_DB_PASSWORD\nbackups:\n  local_path: backups\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\nodoo:\n  image: registry/odoo:latest\n  service: odoo\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /srv/filestore/prod\n    update_modules: [sale, stock]\n    sanitize: true\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /srv/filestore/staging\n    clone_from: production\n    update_modules: [sale]\n    sanitize: true\n"""
    )
    (tmp_path / "docker-compose.yml").touch()

    called: list[str] = []
    monkeypatch.setattr("odooctl.commands.clone.PostgresAdapter", lambda *args, **kwargs: called.append("postgres"))
    monkeypatch.setattr("odooctl.commands.clone.FilestoreAdapter", lambda *args, **kwargs: called.append("filestore"))
    monkeypatch.setattr("odooctl.commands.clone.DockerComposeAdapter", lambda *args, **kwargs: called.append("compose"))
    monkeypatch.setattr("odooctl.commands.clone.check_url", lambda *args, **kwargs: called.append("health"))

    url = execute("production", "staging", True, str(config), sanitization_profile="normal", preview=True)

    assert url == "https://staging.example.com"
    assert called == []
    out = capsys.readouterr().out
    assert "[clone] preview" in out
    assert "source=production" in out
    assert "target=staging" in out
    assert "profile=normal" in out
    assert "base_url=https://staging.example.com" in out
    assert "source_branch=main" in out
    assert "target_branch=staging" in out
    assert "clone_from=production" in out


def test_clone_missing_env_vars_fails_before_dump(tmp_path: Path, monkeypatch):
    config = tmp_path / "odooctl.yml"
    config.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\npostgres:\n  host: localhost\n  port: 5432\n  user: odoo\n  password_env: ODOO_DB_PASSWORD\nbackups:\n  local_path: backups\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\nodoo:\n  image: registry/odoo:latest\n  service: odoo\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /srv/filestore/prod\n    sanitize: true\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /srv/filestore/staging\n    clone_from: production\n    sanitize: true\n"""
    )
    (tmp_path / "docker-compose.yml").touch()

    called: list[str] = []
    monkeypatch.setattr("odooctl.commands.clone.PostgresAdapter", lambda *args, **kwargs: called.append("postgres"))
    monkeypatch.setattr("odooctl.commands.clone.FilestoreAdapter", lambda *args, **kwargs: called.append("filestore"))
    monkeypatch.setattr("odooctl.commands.clone.DockerComposeAdapter", lambda *args, **kwargs: called.append("compose"))
    monkeypatch.delenv("ODOO_DB_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="Missing required environment variables: ODOO_DB_PASSWORD"):
        execute("production", "staging", True, str(config))

    assert called == []


def test_clone_missing_compose_file_fails_before_dump(tmp_path: Path, monkeypatch):
    config = tmp_path / "odooctl.yml"
    config.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: missing-compose.yml\npostgres:\n  host: localhost\n  port: 5432\n  user: odoo\n  password_env: ODOO_DB_PASSWORD\nbackups:\n  local_path: backups\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\nodoo:\n  image: registry/odoo:latest\n  service: odoo\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /srv/filestore/prod\n    sanitize: true\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /srv/filestore/staging\n    clone_from: production\n    sanitize: true\n"""
    )

    called: list[str] = []
    monkeypatch.setattr("odooctl.commands.clone.PostgresAdapter", lambda *args, **kwargs: called.append("postgres"))
    monkeypatch.setattr("odooctl.commands.clone.FilestoreAdapter", lambda *args, **kwargs: called.append("filestore"))
    monkeypatch.setattr("odooctl.commands.clone.DockerComposeAdapter", lambda *args, **kwargs: called.append("compose"))

    with pytest.raises(FileNotFoundError, match="Compose file not found"):
        execute("production", "staging", True, str(config))

    assert called == []


def test_clone_preview_missing_compose_file_fails(tmp_path: Path, monkeypatch):
    config = tmp_path / "odooctl.yml"
    config.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: missing-compose.yml\npostgres:\n  host: localhost\n  port: 5432\n  user: odoo\n  password_env: ODOO_DB_PASSWORD\nbackups:\n  local_path: backups\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\nodoo:\n  image: registry/odoo:latest\n  service: odoo\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /srv/filestore/prod\n    sanitize: true\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /srv/filestore/staging\n    clone_from: production\n    sanitize: true\n"""
    )

    called: list[str] = []
    monkeypatch.setattr("odooctl.commands.clone.PostgresAdapter", lambda *args, **kwargs: called.append("postgres"))
    monkeypatch.setattr("odooctl.commands.clone.FilestoreAdapter", lambda *args, **kwargs: called.append("filestore"))
    monkeypatch.setattr("odooctl.commands.clone.DockerComposeAdapter", lambda *args, **kwargs: called.append("compose"))

    with pytest.raises(FileNotFoundError, match="Compose file not found"):
        execute("production", "staging", True, str(config), preview=True)

    assert called == []


def test_clone_respects_clone_from_mapping(tmp_path: Path, monkeypatch):
    config = tmp_path / "odooctl.yml"
    config.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\npostgres:\n  host: localhost\n  port: 5432\n  user: odoo\n  password_env: ODOO_DB_PASSWORD\nbackups:\n  local_path: backups\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\nodoo:\n  image: registry/odoo:latest\n  service: odoo\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /srv/filestore/prod\n    sanitize: true\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /srv/filestore/staging\n    clone_from: production\n    sanitize: true\n"""
    )
    (tmp_path / "docker-compose.yml").touch()

    monkeypatch.setattr("odooctl.commands.clone.PostgresAdapter", lambda *args, **kwargs: None)
    monkeypatch.setattr("odooctl.commands.clone.FilestoreAdapter", lambda *args, **kwargs: None)
    monkeypatch.setattr("odooctl.commands.clone.DockerComposeAdapter", lambda *args, **kwargs: None)
    monkeypatch.setattr("odooctl.commands.clone.update_modules_compose", lambda *args, **kwargs: None)
    monkeypatch.setattr("odooctl.commands.clone.check_url", lambda *args, **kwargs: None)

    execute("production", "staging", True, str(config), preview=True)


def test_clone_rejects_target_without_clone_from(tmp_path: Path):
    config = tmp_path / "odooctl.yml"
    config.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\npostgres:\n  host: localhost\n  port: 5432\n  user: odoo\n  password_env: ODOO_DB_PASSWORD\nbackups:\n  local_path: backups\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\nodoo:\n  image: registry/odoo:latest\n  service: odoo\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /srv/filestore/prod\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /srv/filestore/staging\n"""
    )

    with pytest.raises(RuntimeError, match="not configured as a clone target"):
        execute("production", "staging", True, str(config), preview=True)


def test_clone_rejects_unexpected_source_for_clone_target(tmp_path: Path):
    config = tmp_path / "odooctl.yml"
    config.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\npostgres:\n  host: localhost\n  port: 5432\n  user: odoo\n  password_env: ODOO_DB_PASSWORD\nbackups:\n  local_path: backups\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\nodoo:\n  image: registry/odoo:latest\n  service: odoo\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /srv/filestore/prod\n  qa:\n    branch: qa\n    domain: qa.example.com\n    db_name: odoo_qa\n    filestore_path: /srv/filestore/qa\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /srv/filestore/staging\n    clone_from: production\n"""
    )

    with pytest.raises(RuntimeError, match="must be cloned from 'production', not 'qa'"):
        execute("qa", "staging", True, str(config), preview=True)


def test_clone_rejects_unsanitized_production_clone_even_in_preview(tmp_path: Path):
    config = tmp_path / "odooctl.yml"
    config.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\npostgres:\n  host: localhost\n  port: 5432\n  user: odoo\n  password_env: ODOO_DB_PASSWORD\nbackups:\n  local_path: backups\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\nodoo:\n  image: registry/odoo:latest\n  service: odoo\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /srv/filestore/prod\n    sanitize: true\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /srv/filestore/staging\n    clone_from: production\n    sanitize: true\n"""
    )

    with pytest.raises(RuntimeError, match="without sanitization enabled"):
        execute("production", "staging", False, str(config), preview=True)


def test_clone_rejects_production_clone_when_target_config_disables_sanitization(tmp_path: Path):
    config = tmp_path / "odooctl.yml"
    config.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\npostgres:\n  host: localhost\n  port: 5432\n  user: odoo\n  password_env: ODOO_DB_PASSWORD\nbackups:\n  local_path: backups\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\nodoo:\n  image: registry/odoo:latest\n  service: odoo\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /srv/filestore/prod\n    sanitize: true\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /srv/filestore/staging\n    clone_from: production\n    sanitize: false\n"""
    )

    with pytest.raises(RuntimeError, match="without sanitization enabled"):
        execute("production", "staging", None, str(config), preview=True)
