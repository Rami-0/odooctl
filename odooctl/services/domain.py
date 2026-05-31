"""Domain/SSL service — attach, verify, detach domains via reverse proxy abstraction."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

import yaml

from odooctl.domains.base import DomainStatus, RouteSpec, ReverseProxyAdapter, resolve_domain

if TYPE_CHECKING:
    from odooctl.services.context import ServiceContext


class DomainService:
    """Orchestrates domain attachment, verification, and detachment.

    The *adapter* must implement the ReverseProxyAdapter protocol (Traefik v1
    in production). Inject a fake for unit tests. The *resolver* and
    *expected_host_ips* parameters allow DNS verification to be controlled
    in tests without real DNS lookups.
    """

    def __init__(
        self,
        ctx: "ServiceContext",
        *,
        adapter: ReverseProxyAdapter,
        resolver: Callable[[str], list[str]] | None = None,
        expected_host_ips: list[str] | None = None,
    ) -> None:
        self._ctx = ctx
        self._adapter = adapter
        self._resolver = resolver
        self._expected_host_ips = expected_host_ips

    def attach(self, environment: str, domain: str) -> None:
        cfg = self._ctx.project.config
        env = cfg.env(environment)
        spec = RouteSpec(
            domain=domain,
            environment=environment,
            scheme=env.scheme,
            port=env.port,
        )
        self._adapter.attach_route(spec)

        # Persist the new domain in the config file if a config path is available
        config_path = self._ctx.project.config_path
        if config_path and config_path.exists():
            raw = yaml.safe_load(config_path.read_text())
            raw.setdefault("environments", {})[environment]["domain"] = domain
            config_path.write_text(yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=False))

    def detach(self, environment: str, domain: str) -> None:
        cfg = self._ctx.project.config
        env = cfg.env(environment)
        if env.domain != domain:
            return
        self._adapter.remove_route(environment)

    def verify(self, environment: str) -> DomainStatus:
        cfg = self._ctx.project.config
        env = cfg.env(environment)
        domain = env.domain

        # Proxy status
        route_status = self._adapter.get_route_status(environment)
        proxy_status = "active" if route_status.active else "inactive"

        # Cert status — inferred from route file for HTTPS; no real ACME probe in v1
        if env.scheme == "https" and route_status.active:
            cert_status = "active"
        elif env.scheme == "https":
            cert_status = "unknown"
        else:
            cert_status = "none"

        # DNS status
        if self._expected_host_ips is None:
            dns_status = "unknown"
            message = "No expected host IPs configured; DNS verification skipped."
        else:
            resolved = resolve_domain(domain, resolver=self._resolver)
            expected_set = set(self._expected_host_ips)
            resolved_set = set(resolved)
            if resolved_set & expected_set:
                dns_status = "ok"
                message = None
            elif not resolved_set:
                dns_status = "failed"
                message = f"Domain {domain!r} did not resolve to any IP."
            else:
                dns_status = "mismatch"
                message = (
                    f"Domain {domain!r} resolved to {sorted(resolved_set)} "
                    f"but expected one of {sorted(expected_set)}."
                )

        return DomainStatus(
            domain=domain,
            environment=environment,
            dns_status=dns_status,
            cert_status=cert_status,
            proxy_status=proxy_status,
            message=message,
        )
