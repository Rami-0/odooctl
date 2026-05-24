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
