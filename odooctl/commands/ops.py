"""ops command — inspect and manage durable operations."""
from __future__ import annotations

import json
import time

import typer
from rich.console import Console
from rich.table import Table

from odooctl.operations.models import OperationStatus
from odooctl.operations.store import OperationStore
from odooctl.services.context import ServiceContext

app = typer.Typer(help="Inspect and manage operations.", add_completion=False)
console = Console()


def _store_and_ctx(config: str) -> tuple[OperationStore, ServiceContext]:
    ctx = ServiceContext.from_config_path(config)
    store = OperationStore(ctx.project.state_dir)
    return store, ctx


@app.command("list")
def list_ops(
    config: str = "odooctl.yml",
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum operations to show."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON array."),
) -> None:
    """List recent operations for this project."""
    store, _ = _store_and_ctx(config)
    ops = store.list_all(limit=limit)
    if json_output:
        typer.echo(json.dumps([json.loads(op.to_json()) for op in ops], indent=2))
        return
    table = Table(title="Operations")
    table.add_column("ID", style="cyan")
    table.add_column("Kind")
    table.add_column("Environment")
    table.add_column("Status")
    table.add_column("Created")
    table.add_column("Actor")
    for op in ops:
        table.add_row(
            op.id,
            op.kind.value,
            op.environment,
            op.status.value,
            op.created_at[:19],
            op.actor,
        )
    console.print(table)


@app.command("show")
def show_op(
    op_id: str = typer.Argument(..., help="Operation ID."),
    config: str = "odooctl.yml",
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Show details for a single operation."""
    store, _ = _store_and_ctx(config)
    try:
        op = store.load(op_id)
    except KeyError:
        typer.echo(f"Operation not found: {op_id}", err=True)
        raise typer.Exit(1)
    if json_output:
        typer.echo(op.to_json())
        return
    typer.echo(op.to_json())


@app.command("logs")
def op_logs(
    op_id: str = typer.Argument(..., help="Operation ID."),
    config: str = "odooctl.yml",
    follow: bool = typer.Option(False, "--follow", "-f", help="Poll until operation completes."),
) -> None:
    """Show event log for an operation."""
    store, _ = _store_and_ctx(config)
    try:
        store.load(op_id)
    except KeyError:
        typer.echo(f"Operation not found: {op_id}", err=True)
        raise typer.Exit(1)

    if not follow:
        for event in store.load_events(op_id):
            _print_event(event)
        return

    seen = 0
    while True:
        events = store.load_events(op_id)
        for event in events[seen:]:
            _print_event(event)
        seen = len(events)
        op = store.load(op_id)
        if op.status in (
            OperationStatus.SUCCEEDED,
            OperationStatus.FAILED,
            OperationStatus.CANCELLED,
        ):
            break
        time.sleep(0.5)


def _print_event(event) -> None:
    typer.echo(
        f"[{event.timestamp[:19]}] [{event.level.upper():5}] [{event.phase}] {event.message}"
    )


@app.command("cancel")
def cancel_op(
    op_id: str = typer.Argument(..., help="Operation ID to cancel."),
    config: str = "odooctl.yml",
) -> None:
    """Cancel a queued or running operation (best-effort)."""
    store, _ = _store_and_ctx(config)
    try:
        op = store.load(op_id)
    except KeyError:
        typer.echo(f"Operation not found: {op_id}", err=True)
        raise typer.Exit(1)
    if op.status not in (OperationStatus.QUEUED, OperationStatus.RUNNING):
        typer.echo(
            f"Operation {op_id} is already {op.status.value}; cannot cancel", err=True
        )
        raise typer.Exit(1)
    store.update_status(op_id, OperationStatus.CANCELLED)
    typer.echo(f"Operation {op_id} cancelled")
