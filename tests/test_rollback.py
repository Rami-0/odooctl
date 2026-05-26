from __future__ import annotations

from pathlib import Path

import pytest
import typer

from odooctl.commands import rollback as rollback_cmd


class DummyCompose:
    def __init__(self, compose_file: str):
        self.compose_file = compose_file
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def up(self, service: str | None = None):
        self.calls.append(("up", (service,)))

    def restart(self, service: str):
        self.calls.append(("restart", (service,)))


CONFIG = """project:
  name: demo
  odoo_version: "19.0"
runtime:
  compose_file: docker-compose.yml
healthcheck:
  path: /web/health
  timeout_seconds: 10
  retries: 3
  interval_seconds: 1
odoo:
  image: registry/odoo:latest
  service: odoo
environments:
  production:
    branch: main
    domain: odoo.example.com
    db_name: odoo_prod
    filestore_path: /srv/filestore/prod
    update_modules: [sale, stock]
    sanitize: true
  staging:
    branch: staging
    domain: staging.example.com
    db_name: odoo_staging
    filestore_path: /srv/filestore/staging
    update_modules: [sale]
    sanitize: true
"""


def write_config(tmp_path: Path) -> Path:
    config = tmp_path / "odooctl.yml"
    config.write_text(CONFIG)
    return config


def test_rollback_code_mode_ups_service_without_restore(tmp_path: Path, monkeypatch, capsys):
    config = write_config(tmp_path)
    compose = DummyCompose("docker-compose.yml")
    restore_calls: list[tuple[object, ...]] = []

    monkeypatch.setattr(rollback_cmd, "DockerComposeAdapter", lambda compose_file: compose)
    monkeypatch.setattr(rollback_cmd, "restore_execute", lambda *args: restore_calls.append(args))

    rollback_cmd.execute("production", "code", None, str(config))

    assert compose.calls == [("up", ("odoo",))]
    assert restore_calls == []
    assert "Code-only rollback" in capsys.readouterr().out


def test_rollback_full_mode_restores_then_ups_service(tmp_path: Path, monkeypatch):
    config = write_config(tmp_path)
    compose = DummyCompose("docker-compose.yml")
    events: list[tuple[str, tuple[object, ...]]] = []

    monkeypatch.setattr(
        rollback_cmd,
        "DockerComposeAdapter",
        lambda compose_file: compose,
    )

    def restore(environment: str, backup: str, config_path: str):
        events.append(("restore", (environment, backup, config_path)))

    def record_up(service: str | None = None):
        events.append(("up", (service,)))
        compose.calls.append(("up", (service,)))

    compose.up = record_up  # type: ignore[method-assign]
    monkeypatch.setattr(rollback_cmd, "restore_execute", restore)

    rollback_cmd.execute("production", "full", "production_2026", str(config))

    assert events == [
        ("restore", ("production", "production_2026", str(config))),
        ("up", ("odoo",)),
    ]
    assert compose.calls == [("up", ("odoo",))]


def test_rollback_full_mode_requires_backup(tmp_path: Path, monkeypatch):
    config = write_config(tmp_path)
    compose = DummyCompose("docker-compose.yml")
    restore_calls: list[tuple[object, ...]] = []

    monkeypatch.setattr(rollback_cmd, "DockerComposeAdapter", lambda compose_file: compose)
    monkeypatch.setattr(rollback_cmd, "restore_execute", lambda *args: restore_calls.append(args))

    with pytest.raises(typer.BadParameter, match="requires --backup"):
        rollback_cmd.execute("production", "full", None, str(config))

    assert restore_calls == []
    assert compose.calls == []


def test_rollback_rejects_invalid_mode(tmp_path: Path, monkeypatch):
    config = write_config(tmp_path)
    called: list[str] = []

    monkeypatch.setattr(rollback_cmd, "DockerComposeAdapter", lambda *args: called.append("compose"))
    monkeypatch.setattr(rollback_cmd, "restore_execute", lambda *args: called.append("restore"))

    with pytest.raises(typer.BadParameter, match="must be code or full"):
        rollback_cmd.execute("production", "partial", None, str(config))

    assert called == []
