from __future__ import annotations
from pathlib import Path
import typer
from odooctl.config import example_config
from odooctl.utils.logging import success, warn

def run(output: str = "odooctl.yml", dry_run: bool = False, force: bool = False) -> None:
    content = example_config()
    path = Path(output)
    if dry_run:
        typer.echo(content)
        return
    if path.exists() and not force:
        raise typer.BadParameter(f"{output} already exists; pass --force to overwrite")
    path.write_text(content)
    success(f"Created {output}")
    warn("Review domains, db names, paths, and environment variable names before deployment.")
