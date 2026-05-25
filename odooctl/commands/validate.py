from __future__ import annotations

import typer

from odooctl.config import load_config
from odooctl.utils.logging import success


def execute(config_path: str = "odooctl.yml") -> None:
    cfg = load_config(config_path)
    env_names = ", ".join(sorted(cfg.environments))
    success(f"Config valid: {cfg.project.name} ({env_names})")


def run(config_path: str = "odooctl.yml") -> None:
    try:
        execute(config_path)
    except Exception as exc:
        raise typer.BadParameter(str(exc)) from exc