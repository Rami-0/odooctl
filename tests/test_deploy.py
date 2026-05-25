from __future__ import annotations

from pathlib import Path

from odooctl.commands import deploy as deploy_cmd


class DummyStore:
    def __init__(self):
        self.saved = []

    def save_deployment(self, metadata):
        self.saved.append(metadata)
        return Path("/tmp/deployment.json")


class DummyCompose:
    def __init__(self, compose_file: str):
        self.compose_file = compose_file
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def pull(self, service: str | None = None):
        self.calls.append(("pull", (service,)))

    def up(self, service: str | None = None):
        self.calls.append(("up", (service,)))

    def restart(self, service: str):
        self.calls.append(("restart", (service,)))


CONFIG = """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\nodoo:\n  image: registry/odoo:latest\n  service: odoo\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /srv/filestore/prod\n    update_modules: [sale, stock]\n    sanitize: true\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /srv/filestore/staging\n    update_modules: [sale]\n    sanitize: true\n"""


def test_deploy_production_runs_backup_pull_update_and_records_metadata(tmp_path: Path, monkeypatch):
    config = tmp_path / "odooctl.yml"
    config.write_text(CONFIG)

    events: list[tuple[str, tuple[object, ...]]] = []
    store = DummyStore()
    compose = DummyCompose("docker-compose.yml")

    monkeypatch.setattr(deploy_cmd, "backup_execute", lambda environment, config_path: events.append(("backup", (environment, config_path))) or "production_2026")
    monkeypatch.setattr(deploy_cmd, "git_commit", lambda: "feedbeef")
    monkeypatch.setattr(deploy_cmd, "run", lambda args, stream=True: events.append(("run", (tuple(args), stream))))
    monkeypatch.setattr(deploy_cmd, "DockerComposeAdapter", lambda compose_file: compose)
    monkeypatch.setattr(deploy_cmd, "update_modules_compose", lambda compose_obj, service, db_name, modules: events.append(("update", (service, db_name, tuple(modules)))))
    monkeypatch.setattr(deploy_cmd, "check_url", lambda url, **kwargs: events.append(("healthcheck", (url, kwargs["timeout"], kwargs["retries"], kwargs["interval"]))))
    monkeypatch.setattr(deploy_cmd, "MetadataStore", lambda: store)

    deploy_cmd.execute("production", "main", str(config))

    assert events[0] == ("backup", ("production", str(config)))
    assert events[1] == ("run", (("git", "fetch", "--all"), True))
    assert events[2] == ("run", (("git", "checkout", "main"), True))
    assert events[3] == ("run", (("git", "pull", "--ff-only"), True))
    assert compose.calls[:2] == [("pull", ("odoo",)), ("up", ("odoo",))]
    assert events[4] == ("update", ("odoo", "odoo_prod", ("sale", "stock")))
    assert events[5] == ("healthcheck", ("https://odoo.example.com/web/health", 10, 3, 1))
    assert store.saved[-1].status == "success"
    assert store.saved[-1].backup == "production_2026"
    assert store.saved[-1].commit == "feedbeef"
    assert store.saved[-1].message is None


def test_deploy_production_restarts_on_failure_and_records_message(tmp_path: Path, monkeypatch):
    config = tmp_path / "odooctl.yml"
    config.write_text(CONFIG)

    store = DummyStore()
    compose = DummyCompose("docker-compose.yml")

    monkeypatch.setattr(deploy_cmd, "backup_execute", lambda environment, config_path: "production_2026")
    monkeypatch.setattr(deploy_cmd, "git_commit", lambda: "feedbeef")
    monkeypatch.setattr(deploy_cmd, "run", lambda args, stream=True: None)
    monkeypatch.setattr(deploy_cmd, "DockerComposeAdapter", lambda compose_file: compose)
    monkeypatch.setattr(deploy_cmd, "update_modules_compose", lambda *args, **kwargs: None)
    monkeypatch.setattr(deploy_cmd, "check_url", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("healthcheck failed")))
    monkeypatch.setattr(deploy_cmd, "MetadataStore", lambda: store)

    try:
        deploy_cmd.execute("production", "main", str(config))
    except RuntimeError:
        pass

    assert compose.calls[-1] == ("restart", ("odoo",))
    assert store.saved[-1].status == "failed"
    assert "healthcheck failed" in (store.saved[-1].message or "")
