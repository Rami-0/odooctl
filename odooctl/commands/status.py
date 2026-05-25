from __future__ import annotations

import json

from rich.console import Console

from odooctl.adapters.docker_compose import DockerComposeAdapter
from odooctl.adapters.reverse_proxy import public_url
from odooctl.commands.backup import git_commit
from odooctl.config import load_config
from odooctl.metadata.store import MetadataStore


def _service_status(ps_output: str, service: str) -> str:
    service_name = service.lower()
    for line in ps_output.splitlines():
        tokens = line.strip().split()
        if not tokens:
            continue
        if tokens[0].lower() == service_name:
            lowered = line.lower()
            if "running" in lowered:
                return "running"
            if "exit" in lowered or "stopped" in lowered:
                return "stopped"
            return "unknown"
    return "unknown"

def execute(config_path: str = "odooctl.yml", environment: str | None = None, *, json_output: bool = False) -> None:
    cfg = load_config(config_path)
    store = MetadataStore()
    console = Console()
    ps = DockerComposeAdapter(cfg.runtime.compose_file).ps()
    env_items = [(environment, cfg.env(environment))] if environment else list(cfg.environments.items())

    def build_environment_payload(name: str, env) -> dict:
        dep = store.latest_deployment(name) or {}
        backup = store.latest_backup(name) or {}
        health_url = dep.get("health_check_url", public_url(env.domain) + cfg.healthcheck.path)
        return {
            "name": name,
            "url": public_url(env.domain),
            "branch": env.branch,
            "commit": dep.get("commit", backup.get("git_commit", "unknown")),
            "image": dep.get("docker_image", backup.get("docker_image", cfg.odoo.image)),
            "odoo": _service_status(ps, cfg.odoo.service),
            "postgresql": _service_status(ps, "postgres"),
            "latest_backup": backup.get("timestamp", "unknown"),
            "last_deployment": dep.get("status", "unknown"),
            "last_deployment_backup": dep.get("backup", "unknown"),
            "last_deployment_message": dep.get("message"),
            "health_check": "passing" if dep.get("status") == "success" else "failing" if dep.get("health_check_url") else dep.get("status", "unknown"),
            "health_check_url": health_url,
        }

    if json_output:
        payload = {
            "project": cfg.project.name,
            "current_git_commit": git_commit() or "unknown",
            "environments": [build_environment_payload(name, env) for name, env in env_items],
        }
        console.print(json.dumps(payload, indent=2, sort_keys=True))
        return

    console.print(f"Project: {cfg.project.name}")
    console.print(f"Current git commit: {git_commit() or 'unknown'}")
    console.print("")
    for name, env in env_items:
        payload = build_environment_payload(name, env)
        console.print(f"Environment: {name}")
        console.print(f"URL: {payload['url']}")
        console.print(f"Branch: {payload['branch']}")
        console.print(f"Commit: {payload['commit']}")
        console.print(f"Image: {payload['image']}")
        console.print(f"Odoo: {payload['odoo']}")
        console.print(f"PostgreSQL: {payload['postgresql']}")
        console.print(f"Latest backup: {payload['latest_backup']}")
        console.print(f"Last deployment: {payload['last_deployment']}")
        if payload['last_deployment_backup'] != 'unknown':
            console.print(f"Deployment backup: {payload['last_deployment_backup']}")
        if payload['last_deployment_message']:
            console.print(f"Deployment message: {payload['last_deployment_message']}")
        console.print(f"Health check: {payload['health_check']}")
        console.print(f"Health check URL: {payload['health_check_url']}")
        console.print("")
    if ps:
        console.print("Docker Compose services:")
        console.print(ps)
