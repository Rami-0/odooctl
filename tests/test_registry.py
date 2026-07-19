from __future__ import annotations

from pathlib import Path

import click
import pytest
from typer.testing import CliRunner

from odooctl.main import app
from odooctl.registry import add_project, load_registry, resolve_project_context, use_project

runner = CliRunner()


def _write_config(root: Path, name: str = "demo") -> Path:
    config = root / "odooctl.yml"
    config.write_text(
        f"""project:\n  name: {name}\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\nenvironments:\n  production:\n    branch: main\n    domain: {name}.example.com\n    db_name: {name}_prod\n    filestore_path: /var/lib/odoo/filestore/{name}_prod\nodoo:\n  image: registry/odoo:latest\n"""
    )
    return config


def test_registry_add_use_remove_round_trip(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, "acme")

    project = add_project("acme", repo)
    assert project.path == repo.resolve()

    registry = load_registry()
    assert registry.active == "acme"
    assert registry.projects["acme"].path == repo.resolve()
    assert registry.path == tmp_path / "xdg" / "odooctl" / "config.toml"

    use_project("acme")
    resolved = resolve_project_context(project="acme")
    assert resolved.root == repo.resolve()
    assert resolved.config.project.name == "acme"


def test_project_command_group_mutates_xdg_registry(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, "acme")

    add_result = runner.invoke(app, ["project", "add", "acme", "--path", str(repo)])
    assert add_result.exit_code == 0, add_result.output
    assert "Registered project acme" in add_result.output

    list_result = runner.invoke(app, ["project", "list", "--json"])
    assert list_result.exit_code == 0, list_result.output
    assert '"active": "acme"' in list_result.output
    assert str(repo.resolve()) in list_result.output

    current_result = runner.invoke(app, ["project", "current"])
    assert current_result.exit_code == 0, current_result.output
    assert "acme" in current_result.output

    remove_result = runner.invoke(app, ["project", "remove", "acme"])
    assert remove_result.exit_code == 0, remove_result.output
    assert load_registry().projects == {}


def test_global_project_option_resolves_registered_project_config(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, "acme")
    add_project("acme", repo)

    result = runner.invoke(app, ["--project", "acme", "validate"])

    assert result.exit_code == 0, result.output
    assert "Config valid: acme (production)" in result.output


def test_project_dir_option_resolves_config_from_non_project_cwd(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, "local")

    result = runner.invoke(app, ["--project-dir", str(repo), "validate"])

    assert result.exit_code == 0, result.output
    assert "Config valid: local (production)" in result.output


# ---- Path containment (audit finding F10) ----


def test_hostile_registry_entry_config_escape_is_rejected(tmp_path: Path, monkeypatch):
    """A hand-edited registry entry whose config escapes the project root must be rejected."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, "acme")
    # A valid config file sitting OUTSIDE the registered project root.
    outside = tmp_path / "outside.yml"
    outside.write_text(_write_config(tmp_path, "evil").read_text())

    registry_file = tmp_path / "xdg" / "odooctl" / "config.toml"
    registry_file.parent.mkdir(parents=True)
    registry_file.write_text(
        'active = "evil"\n\n[projects]\n'
        f'"evil" = {{ path = "{repo}", config = "../outside.yml" }}\n'
    )

    with pytest.raises(click.ClickException, match="escapes the project root"):
        resolve_project_context(project="evil")


def test_hostile_registry_entry_absolute_config_escape_is_rejected(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, "acme")

    registry_file = tmp_path / "xdg" / "odooctl" / "config.toml"
    registry_file.parent.mkdir(parents=True)
    registry_file.write_text(
        'active = "evil"\n\n[projects]\n'
        f'"evil" = {{ path = "{repo}", config = "/etc/passwd" }}\n'
    )

    with pytest.raises(click.ClickException, match="escapes the project root"):
        resolve_project_context(project="evil")


def test_add_project_rejects_config_escaping_root(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, "acme")

    with pytest.raises(click.ClickException, match="escapes the project root"):
        add_project("acme", repo, config="../secrets.yml")


def test_absolute_config_inside_root_still_works(tmp_path: Path, monkeypatch):
    """Legitimate absolute config paths inside the project root keep working."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    repo = tmp_path / "repo"
    repo.mkdir()
    config = _write_config(repo, "acme")

    add_project("acme", repo, config=str(config))
    resolved = resolve_project_context(project="acme")
    assert resolved.root == repo.resolve()
    assert resolved.config.project.name == "acme"


def test_add_project_rejects_hostile_project_name(tmp_path: Path, monkeypatch):
    """F10: project names must satisfy the identifier rule (no path components)."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, "acme")

    for hostile in ("../evil", "a/b", "..", ".hidden", "a b"):
        with pytest.raises(click.ClickException, match="invalid"):
            add_project(hostile, repo)
    assert load_registry().projects == {}


def test_project_add_cli_rejects_hostile_project_name(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, "acme")

    result = runner.invoke(app, ["project", "add", "../evil", "--path", str(repo)])

    assert result.exit_code != 0
    assert "invalid" in result.output.lower()
    assert load_registry().projects == {}
