from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from odooctl.main import app

runner = CliRunner()


def write_config(root: Path) -> Path:
    config = root / "odooctl.yml"
    config.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\npostgres:\n  password_env: ODOO_DB_PASSWORD\nenvironments:\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /var/lib/odoo/filestore/odoo_staging\nodoo:\n  image: registry/odoo:latest\nsanitization:\n  sql_files:\n    - .sanitize/staging.sql\n"""
    )
    return config


def test_doctor_reports_human_failures_for_missing_project_files(tmp_path: Path):
    config = write_config(tmp_path)

    result = runner.invoke(app, ["doctor", "--config", str(config)])

    assert result.exit_code == 1
    assert "Project: demo" in result.output
    assert "[FAIL] compose_file" in result.output
    assert "missing environment variables: ODOO_DB_PASSWORD" in result.output
    assert "sanitization SQL file missing" in result.output


def test_doctor_json_reports_success(tmp_path: Path, monkeypatch):
    config = write_config(tmp_path)
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    (tmp_path / ".sanitize").mkdir()
    (tmp_path / ".sanitize" / "staging.sql").write_text("select 1;\n")
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")

    result = runner.invoke(app, ["doctor", "--config", str(config), "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["project"] == "demo"
    assert payload["root"] == str(tmp_path.resolve())
    assert payload["ok"] is True
    assert {check["name"] for check in payload["checks"]} >= {"config", "project_root", "compose_file", "environment"}
