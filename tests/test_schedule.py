from pathlib import Path

from typer.testing import CliRunner

from odooctl.commands.schedule import render
from odooctl.main import app

runner = CliRunner()


def _write_config(path: Path) -> None:
    path.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /var/lib/odoo/filestore/odoo_prod\nodoo:\n  image: registry/odoo:latest\n"""
    )


def test_render_systemd_timer_for_backup(tmp_path: Path):
    config = tmp_path / "odooctl.yml"
    _write_config(config)

    output = render(
        "backup",
        "production",
        str(config),
        interval="03:15",
        user="odoo",
        odooctl_bin="/usr/local/bin/odooctl",
    )

    assert "# /etc/systemd/system/odooctl-backup-production.service" in output
    assert "WorkingDirectory=" + str(tmp_path) in output
    assert "User=odoo" in output
    assert "ExecStart=/usr/local/bin/odooctl --project-dir" in output
    assert "backup production --config" in output
    assert "OnCalendar=03:15" in output
    assert "Persistent=true" in output


def test_render_cron_alias_for_doctor(tmp_path: Path):
    config = tmp_path / "odooctl.yml"
    _write_config(config)

    output = render("doctor", "production", str(config), format="cron", interval="hourly")

    assert output.startswith("0 * * * * cd ")
    assert "odooctl --project-dir" in output
    assert " doctor production --config " in output


def test_schedule_cli_outputs_cron(tmp_path: Path):
    config = tmp_path / "odooctl.yml"
    _write_config(config)

    result = runner.invoke(
        app,
        [
            "schedule",
            "backup",
            "--env",
            "production",
            "--config",
            str(config),
            "--format",
            "cron",
            "--interval",
            "weekly",
            "--user",
            "odoo",
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.output.startswith("0 2 * * 0 odoo cd ")
    assert "backup production" in result.output


def test_schedule_rejects_unknown_environment(tmp_path: Path):
    config = tmp_path / "odooctl.yml"
    _write_config(config)

    result = runner.invoke(app, ["schedule", "backup", "--env", "staging", "--config", str(config)])

    assert result.exit_code != 0
    assert "Unknown environment: staging" in result.output
