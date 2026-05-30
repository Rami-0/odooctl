"""Branch status command — show per-environment drift and deployment state."""
from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from odooctl.registry import resolve_project_context
from odooctl.services.branch import get_branch_statuses
from odooctl.services.context import ServiceContext

app = typer.Typer(help="Show branch status and drift for each environment.", add_completion=False)
console = Console()


def _ctx(config: str, project: str | None = None, project_dir: str | None = None) -> ServiceContext:
    if project or project_dir is not None:
        pc = resolve_project_context(project=project, project_dir=project_dir, config=config)
        return ServiceContext(project=pc)
    return ServiceContext.from_config_path(config)


@app.command("status")
def branch_status(
    config: str = "odooctl.yml",
    json_output: bool = typer.Option(False, "--json", "--json-output"),
):
    """Show branch, commit, drift, and tier for each configured environment."""
    import click

    ctx_cli = click.get_current_context(silent=True)
    root = ctx_cli.find_root() if ctx_cli is not None else None
    obj = root.obj if root is not None and isinstance(root.obj, dict) else {}
    svc_ctx = _ctx(config, obj.get("project"), obj.get("project_dir"))

    statuses = get_branch_statuses(svc_ctx)

    if json_output:
        typer.echo(
            json.dumps(
                [
                    {
                        "environment": s.environment,
                        "tier": s.tier,
                        "branch": s.branch,
                        "current_commit": s.current_commit,
                        "last_deployed_commit": s.last_deployed_commit,
                        "ahead": s.ahead,
                        "behind": s.behind,
                        "drift": s.drift,
                    }
                    for s in statuses
                ],
                indent=2,
            )
        )
        return

    table = Table(title="Branch status")
    table.add_column("Environment")
    table.add_column("Tier")
    table.add_column("Branch")
    table.add_column("Current")
    table.add_column("Deployed")
    table.add_column("Ahead")
    table.add_column("Behind")
    table.add_column("Drift")

    drift_style = {
        "clean": "green",
        "ahead": "cyan",
        "behind": "yellow",
        "diverged": "red",
        "unknown": "dim",
    }
    for s in statuses:
        style = drift_style.get(s.drift, "")
        table.add_row(
            s.environment,
            s.tier or "-",
            s.branch,
            s.current_commit or "?",
            s.last_deployed_commit or "?",
            str(s.ahead) if s.ahead is not None else "?",
            str(s.behind) if s.behind is not None else "?",
            s.drift,
            style=style,
        )
    console.print(table)
