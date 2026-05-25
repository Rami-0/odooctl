from __future__ import annotations

from pathlib import Path

from odooctl.commands.clone import execute


def test_clone_orchestrates_dump_restore_sanitize_update_and_healthcheck(tmp_path: Path, monkeypatch):
    config = tmp_path / "odooctl.yml"
    config.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\npostgres:\n  host: localhost\n  port: 5432\n  user: odoo\n  password_env: ODOO_DB_PASSWORD\nbackups:\n  local_path: backups\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\nodoo:\n  image: registry/odoo:latest\n  service: odoo\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /srv/filestore/prod\n    update_modules: [sale, stock]\n    sanitize: true\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /srv/filestore/staging\n    update_modules: [sale]\n    sanitize: true\n"""
    )

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

    monkeypatch.setattr("odooctl.commands.clone.PostgresAdapter", DummyPostgres)
    monkeypatch.setattr("odooctl.commands.clone.FilestoreAdapter", DummyFilestore)
    monkeypatch.setattr("odooctl.commands.clone.DockerComposeAdapter", DummyCompose)
    monkeypatch.setattr("odooctl.commands.clone.sanitize_database", lambda *args, **kwargs: events.append(("sanitize", (args[1],))))
    monkeypatch.setattr("odooctl.commands.clone.update_modules_compose", lambda compose, service, db_name, modules: events.append(("update", (service, db_name, tuple(modules)))))
    monkeypatch.setattr("odooctl.commands.clone.check_url", lambda url, **kwargs: events.append(("healthcheck", (url, kwargs["timeout"], kwargs["retries"], kwargs["interval"])) ))
    monkeypatch.chdir(tmp_path)

    url = execute("production", "staging", True, str(config))

    assert url == "https://staging.example.com"
    assert events[0] == ("postgres_init", ("localhost", 5432, "odoo"))
    assert events[1][0] == "dump" and events[1][1][0] == "odoo_prod" and str(events[1][1][1]).endswith(".dump")
    assert events[2][0] == "restore" and events[2][1][0] == "odoo_staging" and str(events[2][1][1]).endswith(".dump")
    assert events[3] == ("copy", ("/srv/filestore/prod", "/srv/filestore/staging"))
    assert events[4] == ("sanitize", ("odoo_staging",))
    assert events[5] == ("compose_init", ("docker-compose.yml",))
    assert events[6] == ("update", ("odoo", "odoo_staging", ("sale",)))
    assert events[7] == ("restart", ("odoo",))
    assert events[8] == ("healthcheck", ("https://staging.example.com/web/health", 10, 3, 1))
    assert len(events) == 9
