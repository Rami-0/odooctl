from __future__ import annotations
import typer
from odooctl.commands.restore import execute as restore_execute
from odooctl.config import load_config
from odooctl.adapters.docker_compose import DockerComposeAdapter
from odooctl.adapters.reverse_proxy import public_url
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
    compose = DockerComposeAdapter(cfg.runtime.compose_file)
    if mode == "code":
        previous = MetadataStore().previous_successful_deployment(environment)
        if not previous or not previous.get("commit"):
            raise RuntimeError(f"No previous successful deployment commit recorded for environment '{environment}'")
        commit = previous["commit"]
        image = previous.get("docker_image") or cfg.odoo.image
        warn("Code-only rollback: redeploying the last successful commit does not restore database or filestore.")
        print(f"[rollback] target commit: {commit}")
        print(f"[rollback] recorded image: {image}")
        run(["git", "fetch", "--all"], stream=True)
        run(["git", "checkout", commit], stream=True)
        compose.up(cfg.odoo.service)
        _verify_health(cfg, environment)
        return
    if not backup:
        raise typer.BadParameter("Full rollback requires --backup")
    warn("Full rollback may discard production data created after the backup.")
    restore_execute(environment, backup, config_path)
    compose.up(cfg.odoo.service)
    _verify_health(cfg, environment)
