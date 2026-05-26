from __future__ import annotations

import json

import typer
from rich.console import Console

from odooctl.context import ProjectContext
from odooctl.preflight import checks_ok, run_preflight


def execute(config_path: str = "odooctl.yml", *, json_output: bool = False) -> None:
    ctx = ProjectContext.from_config_path(config_path)
    checks = run_preflight(ctx)
    console = Console()

    if json_output:
        payload = {
            "project": ctx.config.project.name,
            "root": str(ctx.root),
            "config_path": str(ctx.config_path),
            "ok": checks_ok(checks),
            "checks": [check.__dict__ for check in checks],
        }
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    else:
        console.print(f"Project: {ctx.config.project.name}")
        console.print(f"Root: {ctx.root}")
        console.print(f"Config: {ctx.config_path}")
        console.print("")
        for check in checks:
            marker = "OK" if check.ok else "FAIL"
            console.print(f"[{marker}] {check.name}: {check.message}")

    if not checks_ok(checks):
        raise typer.Exit(1)
