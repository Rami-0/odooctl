from __future__ import annotations
from pathlib import Path

import typer
from odooctl.commands.backup import git_commit
from odooctl.commands.restore import execute as restore_execute
from odooctl.config import load_config
from odooctl.adapters.docker_compose import DockerComposeAdapter
from odooctl.adapters.reverse_proxy import public_url
from odooctl.metadata.models import DeploymentMetadata
from odooctl.metadata.store import MetadataStore
from odooctl.odoo.healthcheck import check_url
from odooctl.utils.logging import warn
from odooctl.utils.shell import run

def _verify_health(cfg, environment: str) -> None:
    url = public_url(cfg.env(environment).domain) + cfg.healthcheck.path
    print("[rollback] verify")
    check_url(
        url,
        timeout=cfg.healthcheck.timeout_seconds,
        retries=cfg.healthcheck.retries,
        interval=cfg.healthcheck.interval_seconds,
    )

def execute(environment: str, mode: str = "code", backup: str | None = None, config_path: str = "odooctl.yml") -> None:
    cfg = load_config(config_path)
    if mode not in {"code", "full"}:
        raise typer.BadParameter("--mode must be code or full")
    if mode == "full" and not backup:
        raise typer.BadParameter("Full rollback requires --backup")
    if mode == "full":
        missing_env_vars = cfg.missing_env_vars()
        if missing_env_vars:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing_env_vars)}")

    compose_path = Path(config_path).parent / cfg.runtime.compose_file
    if not compose_path.exists():
        raise FileNotFoundError(f"Compose file not found: {compose_path}")

    env = cfg.env(environment)
    url = public_url(env.domain) + cfg.healthcheck.path
    compose = DockerComposeAdapter(cfg.runtime.compose_file)
    store = MetadataStore()
    status = "failed"
    message = None
    commit: str | None = git_commit()
    image: str | None = cfg.odoo.image

    if mode == "code":
        previous = store.previous_successful_deployment(environment)
        if not previous or not previous.get("commit"):
            raise RuntimeError(f"No previous successful deployment commit recorded for environment '{environment}'")
        commit = str(previous["commit"])
        previous_image = previous.get("docker_image")
        image = str(previous_image) if previous_image else cfg.odoo.image

    try:
        if mode == "code":
            warn("Code-only rollback: redeploying the last successful commit does not restore database or filestore.")
            print(f"[rollback] target commit: {commit}")
            print(f"[rollback] recorded image: {image}")
            run(["git", "fetch", "--all"], stream=True)
            if commit is None:
                raise RuntimeError("No current git commit available for code rollback metadata")
            run(["git", "checkout", commit], stream=True)
        else:
            if backup is None:
                raise RuntimeError("Full rollback requires a backup id")
            warn("Full rollback may discard production data created after the backup.")
            restore_execute(environment, backup, config_path)
        compose.up(cfg.odoo.service)
        _verify_health(cfg, environment)
        status = "success"
    except Exception as exc:
        message = str(exc)
        raise
    finally:
        store.save_deployment(
            DeploymentMetadata(
                project=cfg.project.name,
                environment=environment,
                branch=env.branch,
                commit=commit,
                docker_image=image,
                backup=backup if mode == "full" else None,
                modules_updated=[],
                status=status,
                health_check_url=url,
                message=f"rollback:{mode}" if message is None else f"rollback:{mode}: {message}",
            )
        )
