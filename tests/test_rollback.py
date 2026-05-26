from __future__ import annotations

from pathlib import Path
from typing import Any

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


class DummyStore:
    def __init__(self, previous: dict[str, object] | None):
        self.previous = previous
        self.saved: list[Any] = []

    def previous_successful_deployment(self, environment: str):
        return self.previous

    def save_deployment(self, deployment):
        self.saved.append(deployment)


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


def write_compose(tmp_path: Path) -> Path:
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}\n")
    return compose


def test_rollback_code_mode_checks_out_previous_successful_commit(tmp_path: Path, monkeypatch, capsys):
    config = write_config(tmp_path)
    write_compose(tmp_path)
    compose = DummyCompose("docker-compose.yml")
    restore_calls: list[tuple[object, ...]] = []
    run_calls: list[list[str]] = []
    health_calls: list[tuple[str, int, int, int]] = []

    store = DummyStore({"status": "success", "commit": "abc123", "docker_image": "registry/odoo:good"})

    monkeypatch.setattr(rollback_cmd, "DockerComposeAdapter", lambda compose_file: compose)
    monkeypatch.setattr(rollback_cmd, "restore_execute", lambda *args: restore_calls.append(args))
    monkeypatch.setattr(rollback_cmd, "MetadataStore", lambda: store)
    monkeypatch.setattr(rollback_cmd, "run", lambda args, **kwargs: run_calls.append(list(args)))
    monkeypatch.setattr(
        rollback_cmd,
        "check_url",
        lambda url, *, timeout, retries, interval: health_calls.append((url, timeout, retries, interval)),
    )

    rollback_cmd.execute("production", "code", None, str(config))

    assert run_calls == [["git", "fetch", "--all"], ["git", "checkout", "abc123"]]
    assert compose.calls == [("up", ("odoo",))]
    assert health_calls == [("https://odoo.example.com/web/health", 10, 3, 1)]
    assert restore_calls == []
    output = capsys.readouterr().out
    assert "Code-only rollback" in output
    assert "target commit: abc123" in output
    assert "recorded image: registry/odoo:good" in output
    assert "[rollback] verify" in output
    assert len(store.saved) == 1
    metadata = store.saved[0]
    assert metadata.environment == "production"
    assert metadata.branch == "main"
    assert metadata.commit == "abc123"
    assert metadata.docker_image == "registry/odoo:good"
    assert metadata.backup is None
    assert metadata.modules_updated == []
    assert metadata.status == "success"
    assert metadata.health_check_url == "https://odoo.example.com/web/health"
    assert metadata.message == "rollback:code"


def test_rollback_code_mode_requires_recorded_successful_commit(tmp_path: Path, monkeypatch):
    config = write_config(tmp_path)
    write_compose(tmp_path)
    compose = DummyCompose("docker-compose.yml")

    monkeypatch.setattr(rollback_cmd, "DockerComposeAdapter", lambda compose_file: compose)
    monkeypatch.setattr(rollback_cmd, "MetadataStore", lambda: DummyStore(None))

    with pytest.raises(RuntimeError, match="No previous successful deployment commit"):
        rollback_cmd.execute("production", "code", None, str(config))

    assert compose.calls == []


def test_rollback_code_mode_rejects_branch_mismatch(tmp_path: Path, monkeypatch):
    config = write_config(tmp_path)
    write_compose(tmp_path)
    compose = DummyCompose("docker-compose.yml")
    run_calls: list[list[str]] = []
    store = DummyStore({"status": "success", "commit": "abc123", "branch": "release", "docker_image": "registry/odoo:good"})

    monkeypatch.setattr(rollback_cmd, "DockerComposeAdapter", lambda compose_file: compose)
    monkeypatch.setattr(rollback_cmd, "MetadataStore", lambda: store)
    monkeypatch.setattr(rollback_cmd, "run", lambda args, **kwargs: run_calls.append(list(args)))

    with pytest.raises(RuntimeError, match="refusing code rollback across branches"):
        rollback_cmd.execute("production", "code", None, str(config))

    assert run_calls == []
    assert compose.calls == []
    assert store.saved == []


def test_rollback_code_mode_allows_matching_branch(tmp_path: Path, monkeypatch):
    config = write_config(tmp_path)
    write_compose(tmp_path)
    compose = DummyCompose("docker-compose.yml")
    run_calls: list[list[str]] = []
    health_calls: list[tuple[str, int, int, int]] = []
    store = DummyStore({"status": "success", "commit": "abc123", "branch": "main", "docker_image": "registry/odoo:good"})

    monkeypatch.setattr(rollback_cmd, "DockerComposeAdapter", lambda compose_file: compose)
    monkeypatch.setattr(rollback_cmd, "MetadataStore", lambda: store)
    monkeypatch.setattr(rollback_cmd, "run", lambda args, **kwargs: run_calls.append(list(args)))
    monkeypatch.setattr(
        rollback_cmd,
        "check_url",
        lambda url, *, timeout, retries, interval: health_calls.append((url, timeout, retries, interval)),
    )

    rollback_cmd.execute("production", "code", None, str(config))

    assert run_calls == [["git", "fetch", "--all"], ["git", "checkout", "abc123"]]
    assert compose.calls == [("up", ("odoo",))]
    assert health_calls == [("https://odoo.example.com/web/health", 10, 3, 1)]
    assert len(store.saved) == 1
    metadata = store.saved[0]
    assert metadata.status == "success"
    assert metadata.branch == "main"
    assert metadata.commit == "abc123"


def test_rollback_full_mode_restores_then_ups_service(tmp_path: Path, monkeypatch):
    config = write_config(tmp_path)
    write_compose(tmp_path)
    compose = DummyCompose("docker-compose.yml")
    events: list[tuple[str, tuple[object, ...]]] = []

    store = DummyStore(None)
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")
    monkeypatch.setattr(
        rollback_cmd,
        "DockerComposeAdapter",
        lambda compose_file: compose,
    )
    monkeypatch.setattr(rollback_cmd, "MetadataStore", lambda: store)
    monkeypatch.setattr(rollback_cmd, "git_commit", lambda: "current123")

    def restore(environment: str, backup: str, config_path: str):
        events.append(("restore", (environment, backup, config_path)))

    def record_up(service: str | None = None):
        events.append(("up", (service,)))
        compose.calls.append(("up", (service,)))

    def record_health(url: str, *, timeout: int, retries: int, interval: int):
        events.append(("healthcheck", (url, timeout, retries, interval)))

    compose.up = record_up  # type: ignore[method-assign]
    monkeypatch.setattr(rollback_cmd, "restore_execute", restore)
    monkeypatch.setattr(rollback_cmd, "check_url", record_health)

    rollback_cmd.execute("production", "full", "production_2026", str(config))

    assert events == [
        ("restore", ("production", "production_2026", str(config))),
        ("up", ("odoo",)),
        ("healthcheck", ("https://odoo.example.com/web/health", 10, 3, 1)),
    ]
    assert compose.calls == [("up", ("odoo",))]
    assert len(store.saved) == 1
    metadata = store.saved[0]
    assert metadata.environment == "production"
    assert metadata.branch == "main"
    assert metadata.commit == "current123"
    assert metadata.docker_image == "registry/odoo:latest"
    assert metadata.backup == "production_2026"
    assert metadata.modules_updated == []
    assert metadata.status == "success"
    assert metadata.health_check_url == "https://odoo.example.com/web/health"
    assert metadata.message == "rollback:full"

def test_rollback_full_mode_requires_env_vars(tmp_path: Path, monkeypatch):
    config = write_config(tmp_path)
    write_compose(tmp_path)
    compose = DummyCompose("docker-compose.yml")
    restore_calls: list[tuple[object, ...]] = []

    monkeypatch.delenv("ODOO_DB_PASSWORD", raising=False)
    monkeypatch.setattr(rollback_cmd, "DockerComposeAdapter", lambda compose_file: compose)
    monkeypatch.setattr(rollback_cmd, "restore_execute", lambda *args: restore_calls.append(args))

    with pytest.raises(RuntimeError, match="Missing required environment variables: ODOO_DB_PASSWORD"):
        rollback_cmd.execute("production", "full", "production_2026", str(config))

    assert restore_calls == []
    assert compose.calls == []

def test_rollback_fails_when_post_rollback_healthcheck_fails(tmp_path: Path, monkeypatch):
    config = write_config(tmp_path)
    write_compose(tmp_path)
    compose = DummyCompose("docker-compose.yml")

    store = DummyStore({"status": "success", "commit": "abc123", "docker_image": "registry/odoo:good"})

    monkeypatch.setattr(rollback_cmd, "DockerComposeAdapter", lambda compose_file: compose)
    monkeypatch.setattr(rollback_cmd, "MetadataStore", lambda: store)
    monkeypatch.setattr(rollback_cmd, "run", lambda args, **kwargs: None)
    monkeypatch.setattr(
        rollback_cmd,
        "check_url",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("healthcheck failed")),
    )

    with pytest.raises(RuntimeError, match="healthcheck failed"):
        rollback_cmd.execute("production", "code", None, str(config))

    assert compose.calls == [("up", ("odoo",))]
    assert len(store.saved) == 1
    metadata = store.saved[0]
    assert metadata.status == "failed"
    assert metadata.message == "rollback:code: healthcheck failed"
    assert metadata.commit == "abc123"

def test_rollback_full_mode_requires_backup(tmp_path: Path, monkeypatch):
    config = write_config(tmp_path)
    write_compose(tmp_path)
    compose = DummyCompose("docker-compose.yml")
    restore_calls: list[tuple[object, ...]] = []

    monkeypatch.setattr(rollback_cmd, "DockerComposeAdapter", lambda compose_file: compose)
    monkeypatch.setattr(rollback_cmd, "restore_execute", lambda *args: restore_calls.append(args))

    with pytest.raises(typer.BadParameter, match="requires --backup"):
        rollback_cmd.execute("production", "full", None, str(config))

    assert restore_calls == []
    assert compose.calls == []


def test_rollback_full_mode_missing_compose_file_fails_before_restore(tmp_path: Path, monkeypatch):
    config = write_config(tmp_path)
    compose = DummyCompose("docker-compose.yml")
    store = DummyStore(None)
    restore_calls: list[tuple[object, ...]] = []

    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")
    monkeypatch.setattr(rollback_cmd, "DockerComposeAdapter", lambda compose_file: compose)
    monkeypatch.setattr(rollback_cmd, "MetadataStore", lambda: store)
    monkeypatch.setattr(rollback_cmd, "restore_execute", lambda *args: restore_calls.append(args))

    with pytest.raises(FileNotFoundError, match="Compose file not found"):
        rollback_cmd.execute("production", "full", "production_2026", str(config))

    assert restore_calls == []
    assert compose.calls == []
    assert store.saved == []


def test_rollback_rejects_invalid_mode(tmp_path: Path, monkeypatch):
    config = write_config(tmp_path)
    called: list[str] = []

    monkeypatch.setattr(rollback_cmd, "DockerComposeAdapter", lambda *args: called.append("compose"))
    monkeypatch.setattr(rollback_cmd, "restore_execute", lambda *args: called.append("restore"))

    with pytest.raises(typer.BadParameter, match="must be code or full"):
        rollback_cmd.execute("production", "partial", None, str(config))

    assert called == []
