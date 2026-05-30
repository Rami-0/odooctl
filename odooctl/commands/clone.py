"""Clone command — thin wrapper around the clone service."""
from __future__ import annotations

from odooctl.services.clone import run_clone
from odooctl.services.context import ServiceContext


def execute(
    source: str,
    target: str,
    sanitize: bool | None = True,
    config_path: str = "odooctl.yml",
    sanitization_profile: str = "normal",
    preview: bool = False,
) -> str:
    ctx = ServiceContext.from_config_path(config_path)
    result = run_clone(ctx, source, target, sanitize=sanitize, sanitization_profile=sanitization_profile, preview=preview)
    return result.url
