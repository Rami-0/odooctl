"""Environment service — read-only queries over environment configuration."""
from __future__ import annotations

from typing import TYPE_CHECKING

from odooctl.adapters.reverse_proxy import public_url
from odooctl.services.models import EnvironmentSummary

if TYPE_CHECKING:
    from odooctl.services.context import ServiceContext


def list_environments(ctx: ServiceContext) -> list[EnvironmentSummary]:
    cfg = ctx.project.config
    result = []
    for name, env in cfg.environments.items():
        scheme = cfg.healthcheck.scheme or env.scheme
        env_url = public_url(env.domain, scheme=scheme, port=env.port)
        result.append(
            EnvironmentSummary(
                name=name,
                url=env_url,
                branch=env.branch,
                commit="unknown",
                image=cfg.odoo.image,
                odoo_status="unknown",
                postgres_status="unknown",
                latest_backup="unknown",
                last_deployment="unknown",
                last_deployment_backup="unknown",
                last_deployment_message=None,
                health_check="unknown",
                health_check_url=env_url + cfg.healthcheck.path,
            )
        )
    return result
