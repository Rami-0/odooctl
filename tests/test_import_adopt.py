"""Tests for the import adoption step (writing odooctl.yml)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from odooctl.importer.adopt import adopt
from odooctl.importer.detect import detect_from_compose
from odooctl.importer.report import build_preview_report
from odooctl.main import app
from odooctl.registry import load_registry

_cli = CliRunner()

MINIMAL_COMPOSE = """\
services:
  db:
    image: postgres:17
    environment:
      POSTGRES_DB: postgres
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: ${ODOO_DB_PASSWORD:-odoo}
    volumes:
      - postgres-data:/var/lib/postgresql/data

  odoo:
    image: odoo:19.0
    environment:
      HOST: db
      USER: odoo
      PASSWORD: ${ODOO_DB_PASSWORD:-odoo}
    ports:
      - "18069:8069"
    volumes:
      - odoo-data:/var/lib/odoo
      - ./addons:/mnt/extra-addons

volumes:
  postgres-data:
  odoo-data:
"""


def _make_report(tmp_path: Path, project_name: str = "myproject"):
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(MINIMAL_COMPOSE)
    detected = detect_from_compose(compose_file)
    return build_preview_report(detected, project_name=project_name)


def test_adopt_writes_odooctl_yml(tmp_path: Path) -> None:
    report = _make_report(tmp_path)
    output = tmp_path / "odooctl.yml"

    adopt(report, output_path=output)

    assert output.exists()


def test_adopt_written_config_is_valid_yaml(tmp_path: Path) -> None:
    report = _make_report(tmp_path)
    output = tmp_path / "odooctl.yml"

    adopt(report, output_path=output)

    cfg = yaml.safe_load(output.read_text())
    assert isinstance(cfg, dict)
    assert "project" in cfg


def test_adopt_written_config_has_correct_project_name(tmp_path: Path) -> None:
    report = _make_report(tmp_path, project_name="acme-erp")
    output = tmp_path / "odooctl.yml"

    adopt(report, output_path=output)

    cfg = yaml.safe_load(output.read_text())
    assert cfg["project"]["name"] == "acme-erp"


def test_adopt_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    report = _make_report(tmp_path)
    output = tmp_path / "odooctl.yml"
    output.write_text("existing config")

    with pytest.raises(FileExistsError):
        adopt(report, output_path=output)


def test_adopt_preserves_existing_when_refused(tmp_path: Path) -> None:
    report = _make_report(tmp_path)
    output = tmp_path / "odooctl.yml"
    output.write_text("existing config")

    try:
        adopt(report, output_path=output)
    except FileExistsError:
        pass

    assert output.read_text() == "existing config"


def test_adopt_overwrites_with_force(tmp_path: Path) -> None:
    report = _make_report(tmp_path)
    output = tmp_path / "odooctl.yml"
    output.write_text("existing config")

    adopt(report, output_path=output, force=True)

    assert output.read_text() != "existing config"
    cfg = yaml.safe_load(output.read_text())
    assert "project" in cfg


def test_adopt_written_config_references_secrets_by_env_var_name(tmp_path: Path) -> None:
    report = _make_report(tmp_path)
    output = tmp_path / "odooctl.yml"

    adopt(report, output_path=output)

    content = output.read_text()
    # Secrets referenced by env var name, never inlined
    assert "ODOO_DB_PASSWORD" in content
    assert "password: " not in content


def test_adopt_does_not_create_file_when_refused(tmp_path: Path) -> None:
    """adopt() must not create an output file if it raises FileExistsError."""
    report = _make_report(tmp_path)
    output = tmp_path / "subfolder" / "odooctl.yml"
    output.parent.mkdir()
    output.write_text("keep me")

    with pytest.raises(FileExistsError):
        adopt(report, output_path=output)

    assert output.read_text() == "keep me"


# ---- TDD: post-adoption registry / validate / doctor / backup behavior ----


def _write_compose(directory: Path) -> None:
    (directory / "docker-compose.yml").write_text(MINIMAL_COMPOSE)


def test_adoption_registers_project_in_registry(tmp_path: Path, monkeypatch) -> None:
    """CLI --yes adoption must call add_project so the project appears in the registry."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _write_compose(tmp_path)
    output = tmp_path / "odooctl.yml"

    result = _cli.invoke(
        app,
        ["import", str(tmp_path), "--yes", "--name", "reg-test",
         "--output", str(output), "--skip-doctor", "--skip-backup"],
    )
    assert result.exit_code == 0, result.output

    assert "reg-test" in load_registry().projects


def test_adoption_calls_validate_after_adoption(tmp_path: Path, monkeypatch) -> None:
    """CLI --yes adoption must run validate; 'Config valid:' must appear in output."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _write_compose(tmp_path)
    output = tmp_path / "odooctl.yml"

    result = _cli.invoke(
        app,
        ["import", str(tmp_path), "--yes", "--name", "val-test",
         "--output", str(output), "--skip-doctor", "--skip-backup"],
    )
    assert result.exit_code == 0, result.output
    assert "Config valid:" in result.output


def test_adoption_runs_doctor_by_default(tmp_path: Path, monkeypatch) -> None:
    """CLI --yes adoption without --skip-doctor must run doctor (Doctor: in output)."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("ODOO_DB_PASSWORD", "a-very-long-enough-secret")
    _write_compose(tmp_path)
    output = tmp_path / "odooctl.yml"

    result = _cli.invoke(
        app,
        ["import", str(tmp_path), "--yes", "--name", "doc-test",
         "--output", str(output), "--skip-backup"],
    )
    assert result.exit_code == 0, result.output
    assert "Doctor:" in result.output


def test_adoption_skip_doctor_flag_suppresses_doctor(tmp_path: Path, monkeypatch) -> None:
    """--skip-doctor must prevent doctor from running (no Doctor: in output)."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _write_compose(tmp_path)
    output = tmp_path / "odooctl.yml"

    result = _cli.invoke(
        app,
        ["import", str(tmp_path), "--yes", "--name", "nodoc-test",
         "--output", str(output), "--skip-doctor", "--skip-backup"],
    )
    assert result.exit_code == 0, result.output
    assert "Doctor:" not in result.output


def test_adoption_runs_backup_by_default(tmp_path: Path, monkeypatch) -> None:
    """CLI --yes adoption without --skip-backup must attempt backup (message in output)."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _write_compose(tmp_path)
    output = tmp_path / "odooctl.yml"

    result = _cli.invoke(
        app,
        ["import", str(tmp_path), "--yes", "--name", "bak-test",
         "--output", str(output), "--skip-doctor"],
    )
    assert result.exit_code == 0, result.output
    assert (
        "Safety backup created" in result.output
        or "Backup after adoption failed" in result.output
    )


def test_adoption_skip_backup_flag_suppresses_backup(tmp_path: Path, monkeypatch) -> None:
    """--skip-backup must prevent backup from running (no backup message in output)."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _write_compose(tmp_path)
    output = tmp_path / "odooctl.yml"

    result = _cli.invoke(
        app,
        ["import", str(tmp_path), "--yes", "--name", "nobak-test",
         "--output", str(output), "--skip-doctor", "--skip-backup"],
    )
    assert result.exit_code == 0, result.output
    assert "Safety backup created" not in result.output
    assert "Backup after adoption failed" not in result.output
