from __future__ import annotations
from odooctl.adapters.docker_compose import DockerComposeAdapter
from odooctl.config import load_config
from odooctl.odoo.module_update import update_modules_compose

def execute(environment: str, modules: list[str] | None = None, config_path: str = "odooctl.yml") -> None:
    cfg = load_config(config_path)
    env = cfg.env(environment)
    selected = modules if modules is not None else env.update_modules
    compose = DockerComposeAdapter(cfg.runtime.compose_file)
    update_modules_compose(compose, cfg.odoo.service, env.db_name, selected)
