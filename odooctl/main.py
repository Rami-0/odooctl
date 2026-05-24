from __future__ import annotations

import typer

from odooctl.commands import (
    backup as backup_cmd,
    clone as clone_cmd,
    deploy as deploy_cmd,
    github_actions as gha_cmd,
    init as init_cmd,
    logs as logs_cmd,
    restore as restore_cmd,
    rollback as rollback_cmd,
    status as status_cmd,
    update_modules as update_cmd,
)

app = typer.Typer(help="Odoo-aware deployment CLI for self-hosted Docker Compose projects.")

@app.command()
def init(output: str = "odooctl.yml", dry_run: bool = False, force: bool = False):
    init_cmd.run(output, dry_run, force)

@app.command()
def deploy(environment: str, branch: str | None = None, config: str = "odooctl.yml"):
    deploy_cmd.execute(environment, branch, config)

@app.command()
def backup(environment: str, config: str = "odooctl.yml"):
    backup_id = backup_cmd.execute(environment, config)
    typer.echo(backup_id)

@app.command()
def restore(environment: str, backup: str = "latest", config: str = "odooctl.yml"):
    restore_cmd.execute(environment, backup, config)

@app.command(name="clone")
def clone_env(source: str, target: str, sanitize: bool = True, config: str = "odooctl.yml"):
    url = clone_cmd.execute(source, target, sanitize, config)
    typer.echo(f"Staging URL: {url}")

@app.command("update-modules")
def update_modules(environment: str, modules: str | None = None, config: str = "odooctl.yml"):
    parsed = [m.strip() for m in modules.split(",")] if modules else None
    update_cmd.execute(environment, parsed, config)

@app.command()
def rollback(environment: str, mode: str = "code", backup: str | None = None, config: str = "odooctl.yml"):
    rollback_cmd.execute(environment, mode, backup, config)

@app.command()
def logs(environment: str, service: str | None = None, config: str = "odooctl.yml"):
    logs_cmd.execute(environment, service, config)

@app.command()
def status(config: str = "odooctl.yml"):
    status_cmd.execute(config)


@app.command(name="github-actions")
def github_actions(config: str = "odooctl.yml", output: str = ".github/workflows/odooctl-deploy.yml", dry_run: bool = False, force: bool = False):
    content = gha_cmd.run(config, output, dry_run, force)
    if dry_run:
        typer.echo(content)


if __name__ == "__main__":
    app()
