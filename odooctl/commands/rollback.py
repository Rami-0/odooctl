from __future__ import annotations
import typer
from odooctl.commands.restore import execute as restore_execute
from odooctl.config import load_config
from odooctl.adapters.docker_compose import DockerComposeAdapter
from odooctl.utils.logging import warn

def execute(environment: str, mode: str = "code", backup: str | None = None, config_path: str = "odooctl.yml") -> None:
    cfg = load_config(config_path)
    if mode not in {"code", "full"}:
        raise typer.BadParameter("--mode must be code or full")
    compose = DockerComposeAdapter(cfg.runtime.compose_file)
    if mode == "code":
        warn("Code-only rollback: redeploying previous image/code does not restore database or filestore.")
        compose.up(cfg.odoo.service)
        return
    if not backup:
        raise typer.BadParameter("Full rollback requires --backup")
    warn("Full rollback may discard production data created after the backup.")
    restore_execute(environment, backup, config_path)
    compose.up(cfg.odoo.service)
