"""Traefik v1 reverse proxy adapter — filesystem-only dynamic config."""
from __future__ import annotations

from pathlib import Path

import yaml

from odooctl.config import validate_hostname, validate_identifier
from odooctl.domains.base import RouteSpec, RouteStatus


class TraefikAdapter:
    """Write/remove Traefik dynamic YAML fragments under *dynamic_dir*.

    Never restarts the global proxy. Traefik hot-reloads files in its
    configured dynamic config directory. Cert lifecycle is handled by
    Traefik ACME; we only write the router/service declaration.
    """

    def __init__(self, dynamic_dir: str | Path) -> None:
        self.dynamic_dir = Path(dynamic_dir)
        self.dynamic_dir.mkdir(parents=True, exist_ok=True)

    def _route_file(self, environment: str) -> Path:
        # Re-validated here so the environment can never smuggle path
        # components into the dynamic config filename, even when called
        # programmatically without going through config load.
        validate_identifier(environment, "environment")
        return self.dynamic_dir / f"odooctl-{environment}.yml"

    def attach_route(self, spec: RouteSpec) -> None:
        # Re-validate at the point of rule construction: a Host() rule must
        # never be built from an unvalidated string (raises ValueError).
        environment = validate_identifier(spec.environment, "environment")
        domain = validate_hostname(spec.domain, "domain")
        router_name = f"odooctl-{environment}"
        service_name = f"odooctl-{environment}"

        backend_port = spec.port or (443 if spec.scheme == "https" else 80)
        backend_scheme = "http"
        backend_url = f"{backend_scheme}://localhost:{backend_port}"

        router: dict = {
            "rule": f"Host(`{domain}`)",
            "service": service_name,
            "entryPoints": ["websecure" if spec.scheme == "https" else "web"],
        }
        if spec.scheme == "https":
            router["tls"] = {"certResolver": "acme"}

        data = {
            "http": {
                "routers": {router_name: router},
                "services": {
                    service_name: {
                        "loadBalancer": {
                            "servers": [{"url": backend_url}],
                        }
                    }
                },
            }
        }
        route_file = self._route_file(spec.environment)
        route_file.write_text(yaml.dump(data, default_flow_style=False, sort_keys=True))

    def remove_route(self, environment: str) -> None:
        route_file = self._route_file(environment)
        if route_file.exists():
            route_file.unlink()

    def get_route_status(self, environment: str) -> RouteStatus:
        route_file = self._route_file(environment)
        if route_file.exists():
            return RouteStatus(active=True, config_path=str(route_file))
        return RouteStatus(active=False, config_path=None)
