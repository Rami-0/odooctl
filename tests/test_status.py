from __future__ import annotations

from pathlib import Path

from odooctl.commands import status as status_cmd


class DummyConsole:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def print(self, *objects, **kwargs) -> None:
        self.lines.append(" ".join(str(obj) for obj in objects))


class DummyCompose:
    def __init__(self, compose_file: str) -> None:
        self.compose_file = compose_file

    def ps(self) -> str:
        return "odoo running\npostgres running"


class DummyStore:
    def latest_deployment(self, environment: str):
        if environment == "production":
            return {
                "status": "success",
                "commit": "abc1234",
                "docker_image": "registry/odoo:abc1234",
                "health_check_url": "https://odoo.example.com/web/login",
            }
        return None

    def latest_backup(self, environment: str):
        if environment == "production":
            return {"timestamp": "2026-05-24T16:00:00Z", "git_commit": "abc1234", "docker_image": "registry/odoo:abc1234"}
        return None



def test_status_reports_metadata_and_services(monkeypatch, tmp_path: Path):
    config = tmp_path / "odooctl.yml"
    config.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /var/lib/odoo/filestore/odoo_prod\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /var/lib/odoo/filestore/odoo_staging\nodoo:\n  image: registry/odoo:latest\n"""
    )
    dummy_console = DummyConsole()
    monkeypatch.setattr(status_cmd, "Console", lambda: dummy_console)
    monkeypatch.setattr(status_cmd, "DockerComposeAdapter", DummyCompose)
    monkeypatch.setattr(status_cmd, "MetadataStore", lambda: DummyStore())
    monkeypatch.setattr(status_cmd, "git_commit", lambda: "feedbeef")

    status_cmd.execute(str(config), "production")

    joined = "\n".join(dummy_console.lines)
    assert "Project: demo" in joined
    assert "Current git commit: feedbeef" in joined
    assert "Environment: production" in joined
    assert "Environment: staging" not in joined
    assert "Commit: abc1234" in joined
    assert "Image: registry/odoo:abc1234" in joined
    assert "Odoo: running" in joined
    assert "PostgreSQL: running" in joined
    assert "Health check: passing" in joined
    assert "Health check URL: https://odoo.example.com/web/login" in joined
    assert "Docker Compose services:" in joined
    assert "odoo running" in joined


def test_status_can_emit_json(monkeypatch, tmp_path: Path):
    config = tmp_path / "odooctl.yml"
    config.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /var/lib/odoo/filestore/odoo_prod\nodoo:\n  image: registry/odoo:latest\n"""
    )
    dummy_console = DummyConsole()
    monkeypatch.setattr(status_cmd, "Console", lambda: dummy_console)
    monkeypatch.setattr(status_cmd, "DockerComposeAdapter", DummyCompose)
    monkeypatch.setattr(status_cmd, "MetadataStore", lambda: DummyStore())
    monkeypatch.setattr(status_cmd, "git_commit", lambda: "feedbeef")

    status_cmd.execute(str(config), "production", json_output=True)

    output = "\n".join(dummy_console.lines)
    assert '"project": "demo"' in output
    assert '"current_git_commit": "feedbeef"' in output
    assert '"health_check": "passing"' in output
    assert '"health_check_url": "https://odoo.example.com/web/login"' in output
