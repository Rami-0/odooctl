"""ServiceContext — thin wrapper around ProjectContext for the service layer."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from odooctl.context import ProjectContext


@dataclass(frozen=True)
class ServiceContext:
    """Resolved project context passed to all service functions."""

    project: ProjectContext

    @classmethod
    def from_config_path(
        cls,
        config_path: str | Path = "odooctl.yml",
        *,
        root: str | Path | None = None,
    ) -> "ServiceContext":
        return cls(project=ProjectContext.from_config_path(config_path, root=root))
