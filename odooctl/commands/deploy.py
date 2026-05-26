from __future__ import annotations

from pathlib import Path

from odooctl.adapters.docker_compose import DockerComposeAdapter
from odooctl.adapters.postgres import PostgresAdapter
from odooctl.adapters.reverse_proxy import public_url
from odooctl.commands.backup import execute as backup_execute, git_commit
from odooctl.config import load_config
from odooctl.metadata.models import DeploymentMetadata
from odooctl.metadata.store import MetadataStore
from odooctl.odoo.healthcheck import check_url
from odooctl.odoo.module_update import update_modules_compose
from odooctl.utils.shell import run


def _preflight(environment: str, branch: str | None, config_path: str):
    cfg = load_config(config_path)
    missing_env_vars = cfg.missing_env_vars()
    if missing_env_vars:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing_env_vars)}")
    env = cfg.env(environment)
    selected_branch = branch or env.branch
    if selected_branch != env.branch:
        raise RuntimeError(f"Branch '{selected_branch}' is not allowed for environment '{environment}'")
    compose_path = Path(config_path).parent / cfg.runtime.compose_file
    if not compose_path.exists():
        raise FileNotFoundError(f"Compose file not found: {compose_path}")
    filestore_path = Path(env.filestore_path)
    if not filestore_path.exists():
        raise FileNotFoundError(f"Target filestore path not found: {filestore_path}")
    try:
        PostgresAdapter(cfg.postgres).ping(env.db_name)
    except Exception as exc:
        raise RuntimeError(
            f"Postgres connectivity check failed for database '{env.db_name}' "
            f"on {cfg.postgres.host}:{cfg.postgres.port}: {exc}"
        ) from exc
    return cfg, env, selected_branch


def execute(environment: str, branch: str | None = None, config_path: str = "odooctl.yml") -> None:
    print("[deploy] preflight")
    cfg, env, selected_branch = _preflight(environment, branch, config_path)
    backup_id = None
    status = "failed"
    message = None
    url = public_url(env.domain) + cfg.healthcheck.path
    compose = DockerComposeAdapter(cfg.runtime.compose_file)
    try:
        if environment == "production":
            print("[deploy] backup")
            backup_id = backup_execute(environment, config_path)
        print("[deploy] rollout")
        run(["git", "fetch", "--all"], stream=True)
        run(["git", "checkout", selected_branch], stream=True)
        run(["git", "pull", "--ff-only"], stream=True)
        compose.pull(cfg.odoo.service)
        compose.up(cfg.odoo.service)
        update_modules_compose(compose, cfg.odoo.service, env.db_name, env.update_modules)
        print("[deploy] verify")
        check_url(url, timeout=cfg.healthcheck.timeout_seconds, retries=cfg.healthcheck.retries, interval=cfg.healthcheck.interval_seconds)
        status = "success"
        print("[deploy] done")
    except Exception as exc:
        message = str(exc)
        if environment == "production":
            try:
                compose.restart(cfg.odoo.service)
            except Exception as recovery_exc:
                message = f"{message}; recovery restart failed: {recovery_exc}"
        raise
    finally:
        MetadataStore().save_deployment(DeploymentMetadata(project=cfg.project.name, environment=environment, branch=selected_branch, commit=git_commit(), docker_image=cfg.odoo.image, backup=backup_id, modules_updated=env.update_modules, status=status, health_check_url=url, message=message))
