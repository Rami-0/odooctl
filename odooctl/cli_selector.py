"""Shared resolution of the global --project/--project-dir CLI selector.

Commands receive the ``typer.Context`` explicitly and pass it here instead of
relying on ``click.get_current_context()`` lookups.
"""
from __future__ import annotations

from pathlib import Path

import click

from odooctl.context import ProjectContext
from odooctl.registry import resolve_project_context


def selector_obj(ctx: click.Context | None) -> dict:
    """Return the root CLI selector obj ({'project': ..., 'project_dir': ...})."""
    root = ctx.find_root() if ctx is not None else None
    return root.obj if root is not None and isinstance(root.obj, dict) else {}


def resolve_config_path(ctx: click.Context | None, config: str, *, normalize: bool = True) -> Path | str:
    """Resolve the effective config path honoring the global project selector.

    When no selector is set, ``normalize=True`` resolves ``config`` through
    ``ProjectContext`` (absolute path); ``normalize=False`` returns the raw
    ``config`` string unchanged.
    """
    obj = selector_obj(ctx)
    project = obj.get("project")
    project_dir = obj.get("project_dir")
    if project or project_dir is not None:
        return resolve_project_context(project=project, project_dir=project_dir, config=config).config_path
    if normalize:
        return ProjectContext.from_config_path(config).config_path
    return config
