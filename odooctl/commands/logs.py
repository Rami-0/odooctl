from __future__ import annotations

from pathlib import Path

from odooctl.adapters.docker_compose import DockerComposeAdapter
from odooctl.context import ProjectContext


def _compose_adapter(compose_file: str, project_root: Path):
    try:
        return DockerComposeAdapter(compose_file, project_dir=str(project_root))
    except TypeError:
        return DockerComposeAdapter(compose_file)


def execute(
    environment: str,
    service: str | None = None,
    config_path: str = "odooctl.yml",
    *,
    follow: bool = True,
    tail: int | None = None,
) -> None:
    context = ProjectContext.from_config_path(config_path)
    cfg = context.config
    cfg.env(environment)
    _compose_adapter(cfg.runtime.compose_file, context.root).logs(service or cfg.odoo.service, follow=follow, tail=tail)
