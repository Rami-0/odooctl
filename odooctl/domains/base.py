"""Reverse proxy abstraction — protocol and shared dataclasses."""
from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Callable, Protocol, runtime_checkable


@dataclass
class RouteSpec:
    domain: str
    environment: str
    scheme: str  # "http" or "https"
    port: int | None


@dataclass
class RouteStatus:
    active: bool
    config_path: str | None


@dataclass
class DomainStatus:
    domain: str
    environment: str
    dns_status: str   # "ok" | "mismatch" | "failed" | "unknown"
    cert_status: str  # "active" | "unknown" | "none"
    proxy_status: str # "active" | "inactive"
    message: str | None


@runtime_checkable
class ReverseProxyAdapter(Protocol):
    def attach_route(self, spec: RouteSpec) -> None: ...
    def remove_route(self, environment: str) -> None: ...
    def get_route_status(self, environment: str) -> RouteStatus: ...


def _default_resolver(domain: str) -> list[str]:
    try:
        results = socket.getaddrinfo(domain, None)
        return list({r[4][0] for r in results})
    except OSError:
        return []


def resolve_domain(
    domain: str,
    *,
    resolver: Callable[[str], list[str]] | None = None,
) -> list[str]:
    fn = resolver if resolver is not None else _default_resolver
    try:
        return fn(domain)
    except Exception:
        return []
