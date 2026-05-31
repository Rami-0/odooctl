"""Migration path matrix — supported Odoo upgrade paths."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_DATA_PATH = Path(__file__).parent / "data" / "paths.yaml"


@dataclass
class MigrationPath:
    from_version: str
    to_version: str
    requires_openupgrade: bool
    notes: str = ""


def load_matrix(data_path: Path | None = None) -> list[MigrationPath]:
    """Load migration paths from the YAML data file."""
    path = data_path or _DATA_PATH
    data = yaml.safe_load(path.read_text())
    return [
        MigrationPath(
            from_version=p["from"],
            to_version=p["to"],
            requires_openupgrade=p.get("requires_openupgrade", True),
            notes=p.get("notes", ""),
        )
        for p in data.get("paths", [])
    ]


def supported_paths(
    from_version: str | None = None,
    to_version: str | None = None,
    data_path: Path | None = None,
) -> list[MigrationPath]:
    """Return paths filtered by optional from/to version constraints."""
    paths = load_matrix(data_path)
    if from_version:
        paths = [p for p in paths if p.from_version == from_version]
    if to_version:
        paths = [p for p in paths if p.to_version == to_version]
    return paths


def format_matrix(paths: list[MigrationPath] | None = None) -> str:
    """Format the migration matrix as a human-readable table."""
    rows = paths if paths is not None else load_matrix()
    header = f"{'From':<8}  {'To':<8}  {'OpenUpgrade':<12}  Notes"
    sep = "-" * 70
    lines = [header, sep]
    for p in rows:
        ou = "required" if p.requires_openupgrade else "optional"
        lines.append(f"{p.from_version:<8}  {p.to_version:<8}  {ou:<12}  {p.notes}")
    if not rows:
        lines.append("  (no paths defined)")
    return "\n".join(lines)
