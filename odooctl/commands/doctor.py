"""Doctor command — thin wrapper: runs preflight checks and renders DoctorReport."""
from __future__ import annotations

import json

import typer
from rich.console import Console

from odooctl.preflight import checks_ok, run_preflight
from odooctl.services.context import ServiceContext
from odooctl.services.models import DoctorReport


def _run_doctor(config_path: str = "odooctl.yml") -> DoctorReport:
    ctx = ServiceContext.from_config_path(config_path)
    checks = run_preflight(ctx.project)
    return DoctorReport(
        project=ctx.project.config.project.name,
        root=str(ctx.project.root),
        config_path=str(ctx.project.config_path),
        ok=checks_ok(checks),
        checks=checks,
    )


def execute(config_path: str = "odooctl.yml", *, json_output: bool = False) -> None:
    report = _run_doctor(config_path)
    console = Console()

    if json_output:
        payload = {
            "project": report.project,
            "root": report.root,
            "config_path": report.config_path,
            "ok": report.ok,
            "checks": [check.__dict__ for check in report.checks],
        }
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    else:
        console.print(f"Project: {report.project}")
        console.print(f"Root: {report.root}")
        console.print(f"Config: {report.config_path}")
        console.print("")
        for check in report.checks:
            marker = "OK" if check.ok else "FAIL"
            console.print(f"[{marker}] {check.name}: {check.message}")

    if not report.ok:
        raise typer.Exit(1)
