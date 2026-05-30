"""Adoption step: write the generated odooctl.yml to disk.

Safety contract:
  - Only writes the odooctl.yml config file.
  - Does not run Docker, restart services, mutate databases, or touch volumes.
  - Refuses to overwrite an existing file unless force=True.
  - Generated config must not contain inline secret values (enforced upstream
    by build_preview_report).
"""
from __future__ import annotations

from pathlib import Path

from odooctl.importer.models import ImportPreviewReport


def adopt(
    report: ImportPreviewReport,
    output_path: Path,
    force: bool = False,
) -> None:
    """Write report.generated_config to output_path.

    Raises FileExistsError if output_path exists and force is False.
    """
    if output_path.exists() and not force:
        raise FileExistsError(
            f"{output_path} already exists. "
            "Pass force=True (or --force on the CLI) to overwrite."
        )
    output_path.write_text(report.generated_config)
