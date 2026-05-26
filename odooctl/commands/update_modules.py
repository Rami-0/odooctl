from __future__ import annotations

from pathlib import Path

from odooctl.adapters.docker_compose import DockerComposeAdapter
from odooctl.context import ProjectContext
from odooctl.odoo.module_update import update_modules_compose


def _compose_adapter(compose_file: str, project_root: Path):
    try:
        return DockerComposeAdapter(compose_file, project_dir=str(project_root))
    except TypeError:
        return DockerComposeAdapter(compose_file)


def execute(environment: str, modules: list[str] | None = None, config_path: str = "odooctl.yml") -> None:
    context = ProjectContext.from_config_path(config_path)
    cfg = context.config
    env = cfg.env(environment)
    selected = modules if modules is not None else env.update_modules
    compose = _compose_adapter(cfg.runtime.compose_file, context.root)
    update_modules_compose(compose, cfg.odoo.service, env.db_name, selected)
