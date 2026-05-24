from __future__ import annotations
from rich.console import Console
from odooctl.adapters.docker_compose import DockerComposeAdapter
from odooctl.adapters.reverse_proxy import public_url
from odooctl.config import load_config
from odooctl.metadata.store import MetadataStore

def execute(config_path: str = "odooctl.yml") -> None:
    cfg = load_config(config_path)
    store = MetadataStore()
    console = Console()
    console.print(f"Project: {cfg.project.name}\n")
    ps = DockerComposeAdapter(cfg.runtime.compose_file).ps()
    for name, env in cfg.environments.items():
        dep = store.latest_deployment(name) or {}
        backup = store.latest_backup(name) or {}
        console.print(f"Environment: {name}")
        console.print(f"URL: {public_url(env.domain)}")
        console.print(f"Branch: {env.branch}")
        console.print(f"Image: {cfg.odoo.image}")
        console.print(f"Latest backup: {backup.get('timestamp', 'unknown')}")
        console.print(f"Last deployment: {dep.get('status', 'unknown')}")
        console.print(f"Health check: {dep.get('health_check_url', public_url(env.domain) + cfg.healthcheck.path)}")
        console.print("")
    if ps:
        console.print("Docker Compose services:")
        console.print(ps)
