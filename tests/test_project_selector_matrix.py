"""Regression matrix for the global --project / --project-dir selector.

Guards against the audit finding C1: the root-callback selector must reach
config resolution for every command that accepts a config, regardless of the
working directory. Command bodies are mocked so destructive operations never
execute; the assertion is purely about which config path the command receives.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from odooctl.main import app

runner = CliRunner()


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """A scratch project directory containing a generated odooctl.yml."""
    proj = tmp_path / "proj"
    proj.mkdir()
    result = runner.invoke(app, ["-C", str(proj), "init", "--output", str(proj / "odooctl.yml")])
    assert result.exit_code == 0, result.output
    assert (proj / "odooctl.yml").exists()
    return proj


@pytest.fixture
def empty_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run each CLI invocation from a directory with no odooctl.yml."""
    cwd = tmp_path / "empty"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return cwd


def _config_of(mock) -> Path | None:
    """Extract the config-path argument from a mocked command call."""
    assert mock.called, "command body was never invoked"
    args, kwargs = mock.call_args
    for value in [*args, *kwargs.values()]:
        if isinstance(value, (str, Path)) and str(value).endswith("odooctl.yml"):
            return Path(value)
    return None


# (cli args after the selector, patch target, mock return value)
COMMAND_MATRIX = [
    (["deploy", "staging"], "odooctl.commands.deploy.execute", None),
    (["backup", "staging"], "odooctl.commands.backup.execute", "bk-1"),
    (["restore", "staging"], "odooctl.commands.restore.execute", "bk-1"),
    (
        ["restore", "production", "--to", "staging"],
        "odooctl.commands.restore.execute_to",
        "bk-1",
    ),
    (["clone", "production", "staging"], "odooctl.commands.clone.execute", "http://x"),
    (
        ["update-modules", "staging", "--modules", "sale"],
        "odooctl.commands.update_modules.execute",
        None,
    ),
    (["rollback", "staging"], "odooctl.commands.rollback.execute", None),
    (["promote", "staging", "production"], "odooctl.commands.promote.execute", None),
    (["logs", "staging"], "odooctl.commands.logs.execute", None),
    (["status"], "odooctl.commands.status.execute", None),
    (["validate"], "odooctl.commands.validate.run", None),
    (["doctor"], "odooctl.commands.doctor.execute", None),
    (
        ["schedule", "backup", "--env", "production"],
        "odooctl.commands.schedule.render",
        "# cron",
    ),
    (
        ["github-actions", "--dry-run"],
        "odooctl.commands.github_actions.run",
        "# workflow",
    ),
]

SELECTORS = ["--project-dir", "-C"]


@pytest.mark.parametrize("selector_flag", SELECTORS)
@pytest.mark.parametrize(
    "cli_args,patch_target,retval",
    COMMAND_MATRIX,
    ids=[" ".join(m[0][:2]) for m in COMMAND_MATRIX],
)
def test_project_dir_selector_reaches_every_command(
    project_dir: Path, empty_cwd: Path, selector_flag: str, cli_args, patch_target, retval
):
    with patch(patch_target, return_value=retval) as mock:
        result = runner.invoke(app, [selector_flag, str(project_dir), *cli_args])
    assert result.exit_code == 0, result.output
    received = _config_of(mock)
    assert received is not None, "no config path reached the command body"
    assert received.parent.resolve() == project_dir.resolve(), (
        f"command received config {received}, expected one inside {project_dir}"
    )


@pytest.mark.parametrize("selector_flag", ["--project", "-p"])
def test_registered_project_selector_resolves_config(
    project_dir: Path, empty_cwd: Path, selector_flag: str
):
    add = runner.invoke(app, ["project", "add", "matrixproj", "--path", str(project_dir)])
    assert add.exit_code == 0, add.output
    with patch("odooctl.commands.validate.run") as mock:
        result = runner.invoke(app, [selector_flag, "matrixproj", "validate"])
    assert result.exit_code == 0, result.output
    received = _config_of(mock)
    assert received is not None and received.parent.resolve() == project_dir.resolve()


def test_no_selector_falls_back_to_cwd_default(project_dir: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(project_dir)
    with patch("odooctl.commands.validate.run") as mock:
        result = runner.invoke(app, ["validate"])
    assert result.exit_code == 0, result.output
    args, kwargs = mock.call_args
    received = [*args, *kwargs.values()][0]
    assert str(received) == "odooctl.yml"


def test_missing_config_without_selector_fails_loudly(empty_cwd: Path):
    result = runner.invoke(app, ["validate"])
    assert result.exit_code != 0


def test_env_subcommand_honors_project_dir(project_dir: Path, empty_cwd: Path):
    result = runner.invoke(app, ["--project-dir", str(project_dir), "env", "list"])
    assert result.exit_code == 0, result.output
    assert "production" in result.output
