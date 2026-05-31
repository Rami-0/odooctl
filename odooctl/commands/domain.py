"""Domain/SSL CLI commands — attach, verify, detach."""
from __future__ import annotations

import typer

app = typer.Typer(help="Manage domain/SSL routes via the configured reverse proxy.")


def _make_service(config_path: str, expected_ips: list[str] | None = None):
    from odooctl.services.context import ServiceContext
    from odooctl.services.domain import DomainService
    from odooctl.domains.traefik import TraefikAdapter

    ctx = ServiceContext.from_config_path(config_path)
    # Dynamic config dir: project state dir / traefik-dynamic, or configurable
    dynamic_dir = ctx.project.state_dir / "traefik-dynamic"
    adapter = TraefikAdapter(dynamic_dir=dynamic_dir)
    return DomainService(ctx, adapter=adapter, expected_host_ips=expected_ips or None)


@app.command()
def attach(
    environment: str = typer.Argument(..., help="Environment name (e.g. production)."),
    domain: str = typer.Argument(..., help="Domain to attach (e.g. odoo.example.com)."),
    config: str = "odooctl.yml",
) -> None:
    """Attach a domain to an environment and configure the reverse proxy route."""
    svc = _make_service(config)
    svc.attach(environment, domain)
    typer.echo(f"Domain {domain!r} attached to {environment!r}.")


@app.command()
def detach(
    environment: str = typer.Argument(..., help="Environment name."),
    domain: str = typer.Argument(..., help="Domain to detach."),
    config: str = "odooctl.yml",
) -> None:
    """Remove the reverse proxy route for an environment domain."""
    svc = _make_service(config)
    svc.detach(environment, domain)
    typer.echo(f"Domain {domain!r} detached from {environment!r}.")


@app.command()
def verify(
    environment: str = typer.Argument(..., help="Environment name."),
    config: str = "odooctl.yml",
    expected_ip: list[str] = typer.Option([], "--expected-ip", help="Expected host IP(s) for DNS verification."),
) -> None:
    """Report DNS, certificate, and proxy status for an environment domain."""
    ips = expected_ip if expected_ip else None
    svc = _make_service(config, expected_ips=ips)
    status = svc.verify(environment)
    typer.echo(f"Domain    : {status.domain}")
    typer.echo(f"DNS       : {status.dns_status}")
    typer.echo(f"Cert      : {status.cert_status}")
    typer.echo(f"Proxy     : {status.proxy_status}")
    if status.message:
        typer.echo(f"Note      : {status.message}")
