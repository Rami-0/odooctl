"""Status command — thin wrapper around the project status service."""
from __future__ import annotations

import json

from rich.console import Console

from odooctl.services.context import ServiceContext
from odooctl.services.project import get_status


def execute(config_path: str = "odooctl.yml", environment: str | None = None, *, json_output: bool = False) -> None:
    ctx = ServiceContext.from_config_path(config_path)
    report = get_status(ctx, environment)
    console = Console()

    if json_output:
        payload = {
            "project": report.project,
            "current_git_commit": report.git_commit,
            "environments": [
                {
                    "name": env.name,
                    "url": env.url,
                    "branch": env.branch,
                    "commit": env.commit,
                    "image": env.image,
                    "odoo": env.odoo_status,
                    "postgresql": env.postgres_status,
                    "latest_backup": env.latest_backup,
                    "last_deployment": env.last_deployment,
                    "last_deployment_backup": env.last_deployment_backup,
                    "last_deployment_message": env.last_deployment_message,
                    "health_check": env.health_check,
                    "health_check_url": env.health_check_url,
                }
                for env in report.environments
            ],
        }
        console.print(json.dumps(payload, indent=2, sort_keys=True))
        return

    console.print(f"Project: {report.project}")
    console.print(f"Current git commit: {report.git_commit}")
    console.print("")
    for env in report.environments:
        console.print(f"Environment: {env.name}")
        console.print(f"URL: {env.url}")
        console.print(f"Branch: {env.branch}")
        console.print(f"Commit: {env.commit}")
        console.print(f"Image: {env.image}")
        console.print(f"Odoo: {env.odoo_status}")
        console.print(f"PostgreSQL: {env.postgres_status}")
        console.print(f"Latest backup: {env.latest_backup}")
        console.print(f"Last deployment: {env.last_deployment}")
        if env.last_deployment_backup != "unknown":
            console.print(f"Deployment backup: {env.last_deployment_backup}")
        if env.last_deployment_message:
            console.print(f"Deployment message: {env.last_deployment_message}")
        console.print(f"Health check: {env.health_check}")
        console.print(f"Health check URL: {env.health_check_url}")
        console.print("")
    if report.raw_compose_output:
        console.print("Docker Compose services:")
        console.print(report.raw_compose_output)
