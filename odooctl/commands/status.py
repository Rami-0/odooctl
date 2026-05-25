from __future__ import annotations
import json
from rich.console import Console
from odooctl.adapters.docker_compose import DockerComposeAdapter
from odooctl.adapters.reverse_proxy import public_url
from odooctl.commands.backup import git_commit
from odooctl.config import load_config
from odooctl.metadata.store import MetadataStore

def _service_status(ps_output: str, service: str) -> str:
    lowered = ps_output.lower()
    if service.lower() in lowered:
        return "running"
    return "unknown"

def execute(config_path: str = "odooctl.yml", environment: str | None = None, *, json_output: bool = False) -> None:
    cfg = load_config(config_path)
    store = MetadataStore()
    console = Console()
    ps = DockerComposeAdapter(cfg.runtime.compose_file).ps()
    env_items = [(environment, cfg.env(environment))] if environment else list(cfg.environments.items())
    if json_output:
        payload = {
            "project": cfg.project.name,
            "current_git_commit": git_commit() or "unknown",
            "environments": [],
        }
        for name, env in env_items:
            dep = store.latest_deployment(name) or {}
            backup = store.latest_backup(name) or {}
            health_url = dep.get('health_check_url', public_url(env.domain) + cfg.healthcheck.path)
            payload["environments"].append(
                {
                    "name": name,
                    "url": public_url(env.domain),
                    "branch": env.branch,
                    "commit": dep.get('commit', backup.get('git_commit', 'unknown')),
                    "image": dep.get('docker_image', backup.get('docker_image', cfg.odoo.image)),
                    "odoo": _service_status(ps, cfg.odoo.service),
                    "postgresql": _service_status(ps, 'postgres'),
                    "latest_backup": backup.get('timestamp', 'unknown'),
                    "last_deployment": dep.get('status', 'unknown'),
                    "health_check": 'passing' if dep.get('status') == 'success' else 'failing' if dep.get('health_check_url') else dep.get('status', 'unknown'),
                    "health_check_url": health_url,
                }
            )
        console.print(json.dumps(payload, indent=2, sort_keys=True))
        return

    console.print(f"Project: {cfg.project.name}")
    console.print(f"Current git commit: {git_commit() or 'unknown'}")
    console.print("")
    for name, env in env_items:
        dep = store.latest_deployment(name) or {}
        backup = store.latest_backup(name) or {}
        health_url = dep.get('health_check_url', public_url(env.domain) + cfg.healthcheck.path)
        console.print(f"Environment: {name}")
        console.print(f"URL: {public_url(env.domain)}")
        console.print(f"Branch: {env.branch}")
        console.print(f"Commit: {dep.get('commit', backup.get('git_commit', 'unknown'))}")
        console.print(f"Image: {dep.get('docker_image', backup.get('docker_image', cfg.odoo.image))}")
        console.print(f"Odoo: {_service_status(ps, cfg.odoo.service)}")
        console.print(f"PostgreSQL: {_service_status(ps, 'postgres')}")
        console.print(f"Latest backup: {backup.get('timestamp', 'unknown')}")
        console.print(f"Last deployment: {dep.get('status', 'unknown')}")
        console.print(f"Health check: {dep.get('status', 'unknown') if dep.get('health_check_url') is None else ('passing' if dep.get('status') == 'success' else 'failing')}")
        console.print(f"Health check URL: {health_url}")
        console.print("")
    if ps:
        console.print("Docker Compose services:")
        console.print(ps)
