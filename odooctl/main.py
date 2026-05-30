from __future__ import annotations

from importlib.metadata import version
from pathlib import Path

import click
import typer
from odooctl.commands import (
    backup as backup_cmd,
    branch as branch_cmd,
    catalog as catalog_cmd,
    clone as clone_cmd,
    deploy as deploy_cmd,
    doctor as doctor_cmd,
    env as env_cmd,
    github_actions as gha_cmd,
    import_cmd,
    init as init_cmd,
    logs as logs_cmd,
    ops as ops_cmd,
    project as project_cmd,
    promote as promote_cmd,
    restore as restore_cmd,
    rollback as rollback_cmd,
    schedule as schedule_cmd,
    setup as setup_cmd,
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
app.add_typer(env_cmd.app, name="env")
app.add_typer(ops_cmd.app, name="ops")
app.add_typer(branch_cmd.app, name="branch")
app.add_typer(catalog_cmd.app, name="catalog")


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
def promote(
    source: str,
    target: str,
    preview: bool = typer.Option(False, "--preview", "--dry-run", help="Show promote plan without side effects."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirm promote to a protected target."),
    config: str = "odooctl.yml",
):
    promote_cmd.execute(source, target, _context_config(config), preview=preview, yes=yes)

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


@app.command()
def schedule(
    command: str = typer.Argument(..., help="odooctl command to schedule: backup or doctor."),
    environment: str = typer.Option(..., "--env", "--environment", help="Environment to target."),
    format: str = typer.Option("systemd", "--format", "-f", help="Output format: systemd or cron."),
    interval: str = typer.Option(
        "daily",
        "--interval",
        "-i",
        "--cron",
        help="systemd OnCalendar value or cron alias/expression.",
    ),
    cron_line: bool = typer.Option(False, "--cron-line", help="Shortcut for --format cron."),
    user: str | None = typer.Option(None, "--user", "-u", help="User for systemd service or /etc/cron.d entry."),
    odooctl_bin: str = typer.Option("odooctl", "--odooctl-bin", help="Path/name of the odooctl executable."),
    config: str = "odooctl.yml",
):
    try:
        content = schedule_cmd.render(
            command,
            environment,
            _context_config(config),
            format="cron" if cron_line else format,
            interval=interval,
            user=user,
            odooctl_bin=odooctl_bin,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(content)


@app.command(name="github-actions")
def github_actions(config: str = "odooctl.yml", output: str = ".github/workflows/odooctl-deploy.yml", dry_run: bool = False, force: bool = False):
    content = gha_cmd.run(_context_config(config), output, dry_run, force)
    if dry_run:
        typer.echo(content)


@app.command(name="import")
def import_project(
    path: Path | None = typer.Argument(None, help="Path to docker-compose.yml or its directory."),
    preview: bool = typer.Option(False, "--preview", help="Show preview only (default behaviour)."),
    name: str | None = typer.Option(None, "--name", "-n", help="Project name for the generated config."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Write odooctl.yml after preview (adoption)."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing odooctl.yml."),
    output: Path = typer.Option(Path("odooctl.yml"), "--output", "-o", help="Output path for generated config."),
    skip_doctor: bool = typer.Option(False, "--skip-doctor", help="Skip preflight doctor checks after adoption."),
    skip_backup: bool = typer.Option(False, "--skip-backup", help="Skip safety backup after adoption."),
) -> None:
    """Import an existing Docker Compose Odoo deployment (read-only detection, then optional adoption).

    Detection is strictly read-only: no containers are touched, no DBs mutated,
    no volumes written, and no secret values are printed or stored.

    Run without --yes to preview. Add --yes to write the generated odooctl.yml.
    Use --force to overwrite an existing file.

    After adoption, the project is registered, config is validated, doctor
    preflight checks run, and a safety backup is created. Use --skip-doctor
    or --skip-backup to suppress those post-adoption steps.
    """
    import_cmd.run(
        path,
        preview=preview,
        name=name,
        yes=yes,
        force=force,
        output=output,
        skip_doctor=skip_doctor,
        skip_backup=skip_backup,
    )


@app.command()
def setup(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip interactive prompts and use defaults."),
    stack: str | None = typer.Option(None, "--stack", help="Stack name (e.g. odoo-19-community)."),
    name: str | None = typer.Option(None, "--name", "-n", help="Project name."),
    output: Path = typer.Option(Path("odooctl.yml"), "--output", "-o", help="Output path."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing odooctl.yml."),
    catalog: Path | None = typer.Option(
        None,
        "--catalog",
        help="Path to a YAML catalog manifest to extend bundled entries for this invocation.",
    ),
) -> None:
    """Scaffold a greenfield Odoo project (new deployment, no existing stack).

    For taking over an existing running deployment, use 'odooctl import' instead.
    Secrets are referenced by env-var name only — never inlined in the generated config.
    Use --catalog to extend the bundled catalog with custom StackTemplate entries.
    """
    setup_cmd.run(yes=yes, stack=stack, name=name, output=output, force=force, catalog=catalog)


if __name__ == "__main__":
    app()
