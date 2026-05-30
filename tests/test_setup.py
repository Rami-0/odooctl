"""Tests for the setup wizard (greenfield project scaffolding)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from odooctl.commands.setup import scaffold_project


def test_scaffold_generates_odooctl_yml(tmp_path: Path) -> None:
    output = tmp_path / "odooctl.yml"

    scaffold_project(project_name="greenfield", output_path=output)

    assert output.exists()


def test_scaffold_config_is_valid_yaml(tmp_path: Path) -> None:
    output = tmp_path / "odooctl.yml"

    scaffold_project(project_name="greenfield", output_path=output)

    cfg = yaml.safe_load(output.read_text())
    assert isinstance(cfg, dict)


def test_scaffold_project_name_in_config(tmp_path: Path) -> None:
    output = tmp_path / "odooctl.yml"

    scaffold_project(project_name="acme-corp", output_path=output)

    cfg = yaml.safe_load(output.read_text())
    assert cfg["project"]["name"] == "acme-corp"


def test_scaffold_config_includes_environments(tmp_path: Path) -> None:
    output = tmp_path / "odooctl.yml"

    scaffold_project(project_name="myproject", output_path=output)

    cfg = yaml.safe_load(output.read_text())
    assert "environments" in cfg
    assert len(cfg["environments"]) > 0


def test_scaffold_references_secrets_not_inline(tmp_path: Path) -> None:
    output = tmp_path / "odooctl.yml"

    scaffold_project(project_name="myproject", output_path=output)

    content = output.read_text()
    assert "password_env" in content
    assert "password: " not in content


def test_scaffold_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    output = tmp_path / "odooctl.yml"
    output.write_text("existing config")

    with pytest.raises(FileExistsError):
        scaffold_project(project_name="greenfield", output_path=output)


def test_scaffold_preserves_existing_when_refused(tmp_path: Path) -> None:
    output = tmp_path / "odooctl.yml"
    output.write_text("existing config")

    try:
        scaffold_project(project_name="greenfield", output_path=output)
    except FileExistsError:
        pass

    assert output.read_text() == "existing config"


def test_scaffold_overwrites_with_force(tmp_path: Path) -> None:
    output = tmp_path / "odooctl.yml"
    output.write_text("existing config")

    scaffold_project(project_name="greenfield", output_path=output, force=True)

    assert output.read_text() != "existing config"
    cfg = yaml.safe_load(output.read_text())
    assert cfg["project"]["name"] == "greenfield"


def test_scaffold_uses_stack_odoo_version(tmp_path: Path) -> None:
    output = tmp_path / "odooctl.yml"

    scaffold_project(project_name="myproject", stack="odoo-17-community", output_path=output)

    cfg = yaml.safe_load(output.read_text())
    assert cfg["project"]["odoo_version"] == "17.0"


def test_scaffold_default_stack_is_odoo19(tmp_path: Path) -> None:
    output = tmp_path / "odooctl.yml"

    scaffold_project(project_name="myproject", output_path=output)

    cfg = yaml.safe_load(output.read_text())
    assert cfg["project"]["odoo_version"] == "19.0"


def test_scaffold_has_postgres_section(tmp_path: Path) -> None:
    output = tmp_path / "odooctl.yml"

    scaffold_project(project_name="myproject", output_path=output)

    cfg = yaml.safe_load(output.read_text())
    assert "postgres" in cfg
    assert "password_env" in cfg["postgres"]


def test_scaffold_has_odoo_section_with_image(tmp_path: Path) -> None:
    output = tmp_path / "odooctl.yml"

    scaffold_project(project_name="myproject", output_path=output)

    cfg = yaml.safe_load(output.read_text())
    assert "odoo" in cfg
    assert "image" in cfg["odoo"]
