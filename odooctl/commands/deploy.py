from __future__ import annotations
from odooctl.adapters.docker_compose import DockerComposeAdapter
from odooctl.adapters.reverse_proxy import public_url
from odooctl.commands.backup import execute as backup_execute, git_commit
from odooctl.config import load_config
from odooctl.metadata.models import DeploymentMetadata
from odooctl.metadata.store import MetadataStore
from odooctl.odoo.healthcheck import check_url
from odooctl.odoo.module_update import update_modules_compose
from odooctl.utils.shell import run


def execute(environment: str, branch: str | None = None, config_path: str = "odooctl.yml") -> None:
    cfg = load_config(config_path)
    env = cfg.env(environment)
    selected_branch = branch or env.branch
    backup_id = None
    status = "failed"
    message = None
    url = public_url(env.domain) + cfg.healthcheck.path
    compose = DockerComposeAdapter(cfg.runtime.compose_file)
    try:
        if environment == "production":
            backup_id = backup_execute(environment, config_path)
        run(["git", "fetch", "--all"], stream=True)
        run(["git", "checkout", selected_branch], stream=True)
        run(["git", "pull", "--ff-only"], stream=True)
        compose.pull(cfg.odoo.service)
        compose.up(cfg.odoo.service)
        update_modules_compose(compose, cfg.odoo.service, env.db_name, env.update_modules)
        check_url(url, timeout=cfg.healthcheck.timeout_seconds, retries=cfg.healthcheck.retries, interval=cfg.healthcheck.interval_seconds)
        status = "success"
    except Exception as exc:
        message = str(exc)
        if environment == "production":
            try:
                compose.restart(cfg.odoo.service)
            except Exception as rollback_exc:
                message = f"{message}; rollback restart failed: {rollback_exc}"
        raise
    finally:
        MetadataStore().save_deployment(DeploymentMetadata(project=cfg.project.name, environment=environment, branch=selected_branch, commit=git_commit(), docker_image=cfg.odoo.image, backup=backup_id, modules_updated=env.update_modules, status=status, health_check_url=url, message=message))
