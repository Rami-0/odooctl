from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import click
import typer
import yaml
from rich.console import Console
from rich.table import Table

from odooctl.adapters.db import make_db_adapter
from odooctl.adapters.filestore import make_filestore_adapter
from odooctl.config import load_config
from odooctl.context import ProjectContext
from odooctl.registry import resolve_project_context

app = typer.Typer(help="Manage named Odoo environments in this project.", add_completion=False)
console = Console()


def _config_path(config: str) -> Path:
    ctx = click.get_current_context(silent=True)
    root = ctx.find_root() if ctx is not None else None
    obj = root.obj if root is not None and isinstance(root.obj, dict) else {}
    project = obj.get("project")
    project_dir = obj.get("project_dir")
    if project or project_dir is not None:
        return resolve_project_context(project=project, project_dir=project_dir, config=config).config_path
    return ProjectContext.from_config_path(config).config_path


def _load_raw(path: Path) -> dict:
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise click.ClickException(f"Config file must contain a YAML mapping: {path}")
    data.setdefault("environments", {})
    if not isinstance(data["environments"], dict):
        raise click.ClickException("Config key 'environments' must be a mapping")
    return data


def _write_raw(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False))


@app.command("list")
def list_envs(
    config: str = "odooctl.yml",
    json_output: bool = typer.Option(False, "--json", "--json-output"),
):
    cfg = load_config(_config_path(config))
    if json_output:
        import json

        typer.echo(
            json.dumps(
                {
                    name: env.model_dump(mode="json", exclude_none=True)
                    for name, env in sorted(cfg.environments.items())
                },
                indent=2,
            )
        )
        return

    table = Table(title="odooctl environments")
    table.add_column("Name")
    table.add_column("Branch")
    table.add_column("URL")
    table.add_column("DB")
    table.add_column("Clone from")
    table.add_column("Sanitize")
    for name, env in sorted(cfg.environments.items()):
        port = f":{env.port}" if env.port else ""
        selector = f"?db={env.db_name}" if env.db_selector else ""
        table.add_row(
            name,
            env.branch,
            f"{env.scheme}://{env.domain}{port}{selector}",
            env.db_name,
            env.clone_from or "",
            "yes" if env.sanitize else "no",
        )
    console.print(table)


@app.command("show")
def show_env(
    name: str,
    config: str = "odooctl.yml",
    json_output: bool = typer.Option(False, "--json", "--json-output"),
):
    cfg = load_config(_config_path(config))
    env = cfg.env(name)
    if json_output:
        import json

        typer.echo(json.dumps(env.model_dump(mode="json", exclude_none=True), indent=2))
        return
    typer.echo(yaml.safe_dump({name: env.model_dump(exclude_none=True)}, sort_keys=False).rstrip())


@app.command("create")
def create_env(
    name: str,
    clone_from: str = typer.Option(..., "--clone-from", help="Source environment to clone from."),
    branch: str | None = typer.Option(None, "--branch", help="Git branch for the new environment."),
    domain: str | None = typer.Option(None, "--domain", help="Public domain/host for the new environment."),
    scheme: str = typer.Option("https", "--scheme", help="URL scheme: http or https."),
    port: int | None = typer.Option(None, "--port", help="Optional URL port."),
    db_name: str | None = typer.Option(None, "--db-name", help="Database name; defaults to <project>_<env>."),
    filestore_path: str | None = typer.Option(None, "--filestore-path", help="Filestore path/subpath; defaults from DB name."),
    stack: str | None = typer.Option(None, "--stack", help="Compose stack identity; defaults to source stack."),
    db_selector: bool = typer.Option(False, "--db-selector", help="Append ?db=<db> to probes for shared-stack multi-db."),
    sanitize: bool = typer.Option(True, "--sanitize/--no-sanitize", help="Sanitize data while provisioning."),
    provision: bool = typer.Option(True, "--provision/--no-provision", help="Run safe clone after writing config."),
    config: str = "odooctl.yml",
):
    if name == "production":
        raise click.ClickException("Refusing to create or replace the production environment")
    if scheme not in {"http", "https"}:
        raise click.ClickException("--scheme must be 'http' or 'https'")

    path = _config_path(config)
    data = _load_raw(path)
    if name in data["environments"]:
        raise click.ClickException(f"Environment already exists: {name}")

    current = load_config(path)
    source = current.env(clone_from)
    project_name = current.project.name.replace("-", "_")
    new_db = db_name or f"{project_name}_{name}"
    source_filestore = str(source.filestore_path)
    if filestore_path is None:
        if source.db_name in source_filestore:
            filestore_path = source_filestore.replace(source.db_name, new_db)
        else:
            filestore_path = f"/var/lib/odoo/filestore/{new_db}"

    env_data = {
        "stack": stack or source.stack,
        "branch": branch or name,
        "scheme": scheme,
        "domain": domain or f"{name}.{source.domain}",
        "db_name": new_db,
        "filestore_path": filestore_path,
        "clone_from": clone_from,
        "sanitize": sanitize,
        "db_selector": db_selector,
    }
    if port is not None:
        env_data["port"] = port
    if source.filestore_volume:
        env_data["filestore_volume"] = source.filestore_volume
    if source.update_modules:
        env_data["update_modules"] = list(source.update_modules)

    updated = deepcopy(data)
    updated["environments"][name] = env_data
    # Validate before writing so failed creations do not corrupt the operator config.
    from odooctl.config import OdooCtlConfig

    OdooCtlConfig.model_validate(updated)
    _write_raw(path, updated)
    typer.echo(f"Created environment {name} in {path}")

    if provision:
        from odooctl.services.clone import run_clone
        from odooctl.services.context import ServiceContext
        run_clone(ServiceContext.from_config_path(str(path)), clone_from, name, sanitize=sanitize)
        typer.echo(f"Provisioned {name} from {clone_from}")


@app.command("destroy")
def destroy_env(
    name: str,
    purge: bool = typer.Option(False, "--purge", help="Also purge the non-production DB and filestore before removing config."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirm destructive config removal."),
    config: str = "odooctl.yml",
):
    if name == "production":
        raise click.ClickException("Refusing to destroy the production environment")
    path = _config_path(config)
    data = _load_raw(path)
    if name not in data["environments"]:
        raise click.ClickException(f"Unknown environment: {name}")
    if not yes:
        raise click.ClickException("Pass --yes to confirm environment removal")
    cfg = load_config(path)
    env = cfg.env(name)
    if purge:
        ctx = ProjectContext(path.parent, path, cfg)
        db = make_db_adapter(ctx)
        fs = make_filestore_adapter(ctx, env)
        db.drop(env.db_name)
        fs.delete(str(env.filestore_path))
    updated = deepcopy(data)
    del updated["environments"][name]
    from odooctl.config import OdooCtlConfig

    OdooCtlConfig.model_validate(updated)
    _write_raw(path, updated)
    typer.echo(f"Removed environment {name} from {path}")
