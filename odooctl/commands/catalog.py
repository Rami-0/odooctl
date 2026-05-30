"""odooctl catalog — list, inspect, and validate catalog entries."""
from __future__ import annotations

from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

from odooctl.catalog.registry import get_entry, list_entries, load_manifest

app = typer.Typer(help="Manage the odooctl stack and addon catalog.", add_completion=False)
console = Console()


def _kind_label(entry) -> str:
    return type(entry).__name__


@app.command("list")
def catalog_list() -> None:
    """List all catalog entries (bundled stack templates, addon sources, companions)."""
    entries = list_entries()
    table = Table(title="Catalog")
    table.add_column("ID", style="bold")
    table.add_column("Kind")
    table.add_column("Description")
    for entry in entries:
        table.add_row(entry.id, _kind_label(entry), entry.description)
    console.print(table)


@app.command("show")
def catalog_show(id: str = typer.Argument(..., help="Catalog entry ID.")) -> None:
    """Show all fields for a catalog entry."""
    entry = get_entry(id)
    if entry is None:
        typer.echo(f"No catalog entry with ID: {id}", err=True)
        raise typer.Exit(1)
    console.print(yaml.dump(entry.model_dump(), default_flow_style=False, sort_keys=False))


@app.command("add")
def catalog_add(
    manifest: Path = typer.Argument(..., help="Path to a YAML catalog manifest to validate."),
) -> None:
    """Validate a user manifest and report the IDs it defines.

    This command validates the manifest schema and prints the entry IDs that
    would be added to the catalog. It does not persist state — to use these
    entries in commands that support --catalog, pass the manifest path there.
    """
    if not manifest.exists():
        typer.echo(f"Manifest not found: {manifest}", err=True)
        raise typer.Exit(1)
    try:
        entries = load_manifest(manifest)
    except Exception as exc:
        typer.echo(f"Manifest validation failed: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"Loaded {len(entries)} entr{'y' if len(entries) == 1 else 'ies'} from {manifest}:")
    for entry in entries:
        typer.echo(f"  {_kind_label(entry)}: {entry.id}")
