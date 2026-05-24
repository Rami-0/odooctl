from pathlib import Path

from typer.testing import CliRunner

from odooctl.main import app


runner = CliRunner()


def test_help_lists_core_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "init" in result.output
    assert "deploy" in result.output
    assert "clone" in result.output
    assert "github-actions" in result.output


def test_init_dry_run_prints_example_config(tmp_path: Path):
    result = runner.invoke(app, ["init", "--dry-run", "--output", str(tmp_path / "ignored.yml")])
    assert result.exit_code == 0, result.output
    assert "project:" in result.output
    assert "environments:" in result.output
    assert "password_env: ODOO_DB_PASSWORD" in result.output


def test_module_invocation_entrypoint_smoke(tmp_path: Path):
    # Ensure the module is executable via `python -m odooctl.main` once the __main__ guard is present.
    result = runner.invoke(app, ["status", "--config", str(tmp_path / "missing.yml")])
    assert result.exit_code != 0
    assert "Config file not found" in result.output


def test_logs_command_accepts_tail_and_no_follow(tmp_path: Path, monkeypatch):
    config = tmp_path / "odooctl.yml"
    config.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\nenvironments:\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /var/lib/odoo/filestore/odoo_staging\nodoo:\n  image: registry/odoo:latest\n  service: odoo\n"""
    )

    recorded: dict[str, object] = {}

    class DummyCompose:
        def __init__(self, compose_file: str) -> None:
            recorded["compose_file"] = compose_file

        def logs(self, service: str | None = None, *, follow: bool = True, tail: int | None = None) -> None:
            recorded["service"] = service
            recorded["follow"] = follow
            recorded["tail"] = tail

    monkeypatch.setattr("odooctl.commands.logs.DockerComposeAdapter", DummyCompose)

    result = runner.invoke(app, ["logs", "staging", "--config", str(config), "--no-follow", "--tail", "50"])

    assert result.exit_code == 0, result.output
    assert recorded == {"compose_file": "docker-compose.yml", "service": "odoo", "follow": False, "tail": 50}
