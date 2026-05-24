from __future__ import annotations
from odooctl.adapters.docker_compose import DockerComposeAdapter
from odooctl.config import load_config

def execute(environment: str, service: str | None = None, config_path: str = "odooctl.yml") -> None:
    cfg = load_config(config_path)
    DockerComposeAdapter(cfg.runtime.compose_file).logs(service or cfg.odoo.service)
