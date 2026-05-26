from __future__ import annotations

from importlib.metadata import version
from pathlib import Path

import click
import typer
from odooctl.commands import (
    backup as backup_cmd,
    clone as clone_cmd,
    deploy as deploy_cmd,
    doctor as doctor_cmd,
    github_actions as gha_cmd,
    init as init_cmd,
    logs as logs_cmd,
    project as project_cmd,
    restore as restore_cmd,
    rollback as rollback_cmd,
    status as status_cmd,
    update_modules as update_cmd,
    validate as validate_cmd,
)
from odooctl.registry import resolve_project_context

app = typer.Typer(
    help="Odoo-aware deployment CLI for self-hosted Docker Compose projects.",
    add_completion=False,
)
app.add_typer(project_cmd.app, name="project")


def _context_config(config: str) -> str:
    ctx = click.get_current_context(silent=True)
    root = ctx.find_root() if ctx is not None else None
    obj = root.obj if root is not None and isinstance(root.obj, dict) else {}
    project = obj.get("project")
    project_dir = obj.get("project_dir")
    if not project and project_dir is None:
        return config
    project_context = resolve_project_context(project=project, project_dir=project_dir, config=config)
    return str(project_context.config_path)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version_option: bool = typer.Option(False, "--version", help="Show the installed odooctl version and exit."),
    project: str | None = typer.Option(None, "--project", "-p", help="Registered project name to operate on."),
    project_dir: Path | None = typer.Option(None, "--project-dir", "-C", help="Project directory for ad-hoc operation."),
):
    ctx.obj = {"project": project, "project_dir": project_dir}
    if version_option:
        typer.echo(f"odooctl {version('odooctl')}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command()
def init(output: str = "odooctl.yml", dry_run: bool = False, force: bool = False):
    init_cmd.run(output, dry_run, force)

@app.command()
def deploy(environment: str, branch: str | None = None, config: str = "odooctl.yml"):
    deploy_cmd.execute(environment, branch, _context_config(config))

@app.command()
def backup(environment: str, config: str = "odooctl.yml"):
    backup_id = backup_cmd.execute(environment, _context_config(config))
    typer.echo(backup_id)

@app.command()
def restore(environment: str, backup: str = "latest", config: str = "odooctl.yml"):
    backup_id = restore_cmd.execute(environment, backup, _context_config(config))
    typer.echo(f"Restored {environment} from backup {backup_id}")

@app.command(name="clone")
def clone_env(
    source: str,
    target: str,
    sanitize: bool = True,
    config: str = "odooctl.yml",
    sanitization_profile: str = typer.Option("normal", "--sanitization-profile", "--profile"),
    preview: bool = typer.Option(False, "--preview", "--dry-run"),
):
    url = clone_cmd.execute(source, target, sanitize, _context_config(config), sanitization_profile, preview)
    typer.echo(f"Staging URL: {url}")

@app.command("update-modules")
def update_modules(environment: str, modules: str | None = None, config: str = "odooctl.yml"):
    parsed = [m.strip() for m in modules.split(",")] if modules else None
    update_cmd.execute(environment, parsed, _context_config(config))

@app.command()
def rollback(environment: str, mode: str = "code", backup: str | None = None, config: str = "odooctl.yml"):
    rollback_cmd.execute(environment, mode, backup, _context_config(config))

@app.command()
def logs(environment: str, service: str | None = None, config: str = "odooctl.yml", follow: bool = True, tail: int | None = None):
    logs_cmd.execute(environment, service, _context_config(config), follow=follow, tail=tail)

@app.command()
def status(
    config: str = "odooctl.yml",
    environment: str | None = None,
    json_output: bool = typer.Option(False, "--json", "--json-output"),
):
    status_cmd.execute(_context_config(config), environment, json_output=json_output)


@app.command()
def validate(config: str = "odooctl.yml"):
    validate_cmd.run(_context_config(config))


@app.command()
def doctor(
    config: str = "odooctl.yml",
    json_output: bool = typer.Option(False, "--json", "--json-output"),
):
    doctor_cmd.execute(_context_config(config), json_output=json_output)


@app.command(name="github-actions")
def github_actions(config: str = "odooctl.yml", output: str = ".github/workflows/odooctl-deploy.yml", dry_run: bool = False, force: bool = False):
    content = gha_cmd.run(_context_config(config), output, dry_run, force)
    if dry_run:
        typer.echo(content)


if __name__ == "__main__":
    app()
