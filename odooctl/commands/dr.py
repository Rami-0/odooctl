"""Disaster recovery CLI commands."""
from __future__ import annotations

import typer

app = typer.Typer(help="Disaster recovery drills.")


@app.command()
def drill(
    environment: str = typer.Argument(..., help="Source environment whose latest backup to drill."),
    config: str = "odooctl.yml",
) -> None:
    """Run a DR drill: restore the latest backup into a throwaway DB, healthcheck, then clean up."""
    from odooctl.services.context import ServiceContext
    from odooctl.services.dr import run_dr_drill
    from odooctl.adapters.db import make_db_adapter as make_context_db_adapter
    from odooctl.adapters.filestore import FilestoreAdapter

    ctx = ServiceContext.from_config_path(config)
    cfg = ctx.project.config

    db_adapter = make_context_db_adapter(ctx.project)
    fs_adapter = FilestoreAdapter()

    def healthcheck_fn(url: str) -> bool:
        try:
            from odooctl.odoo.healthcheck import check_url
            check_url(url, timeout=cfg.healthcheck.timeout_seconds, retries=1, interval=1)
            return True
        except Exception:
            return False

    result = run_dr_drill(
        environment=environment,
        backups_root=ctx.project.backups_dir,
        db_adapter=db_adapter,
        fs_adapter=fs_adapter,
        healthcheck_fn=healthcheck_fn,
        is_protected_fn=cfg.is_protected,
    )

    typer.echo(f"DR drill for {environment!r}: {result.status}")
    if result.backup_id:
        typer.echo(f"Backup used: {result.backup_id}")
    if result.message:
        typer.echo(f"Note: {result.message}")

    if result.status != "success":
        raise typer.Exit(code=1)
