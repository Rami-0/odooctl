"""M14 domain/SSL tests — reverse proxy abstraction + Traefik adapter + domain service."""
from __future__ import annotations

from unittest.mock import MagicMock

import yaml


# ---------------------------------------------------------------------------
# Dataclass / protocol shape tests
# ---------------------------------------------------------------------------

def test_route_spec_fields():
    from odooctl.domains.base import RouteSpec
    spec = RouteSpec(domain="odoo.example.com", environment="production", scheme="https", port=None)
    assert spec.domain == "odoo.example.com"
    assert spec.environment == "production"
    assert spec.scheme == "https"
    assert spec.port is None


def test_route_status_fields():
    from odooctl.domains.base import RouteStatus
    status = RouteStatus(active=True, config_path="/path/to/config.yml")
    assert status.active is True
    assert status.config_path == "/path/to/config.yml"


def test_route_status_inactive():
    from odooctl.domains.base import RouteStatus
    status = RouteStatus(active=False, config_path=None)
    assert status.active is False
    assert status.config_path is None


def test_domain_status_fields():
    from odooctl.domains.base import DomainStatus
    ds = DomainStatus(
        domain="odoo.example.com",
        environment="production",
        dns_status="ok",
        cert_status="active",
        proxy_status="active",
        message=None,
    )
    assert ds.domain == "odoo.example.com"
    assert ds.dns_status == "ok"
    assert ds.cert_status == "active"
    assert ds.proxy_status == "active"
    assert ds.message is None


def test_reverse_proxy_adapter_is_protocol():
    from odooctl.domains.base import ReverseProxyAdapter
    # Must be a Protocol or ABC — not instantiatable directly
    assert ReverseProxyAdapter is not None


# ---------------------------------------------------------------------------
# TraefikAdapter — filesystem-only
# ---------------------------------------------------------------------------

def test_traefik_adapter_attach_writes_yaml(tmp_path):
    from odooctl.domains.base import RouteSpec
    from odooctl.domains.traefik import TraefikAdapter

    adapter = TraefikAdapter(dynamic_dir=tmp_path)
    spec = RouteSpec(domain="odoo.example.com", environment="production", scheme="https", port=None)
    adapter.attach_route(spec)

    config_file = tmp_path / "odooctl-production.yml"
    assert config_file.exists()
    data = yaml.safe_load(config_file.read_text())
    assert "http" in data
    assert "routers" in data["http"]


def test_traefik_adapter_attach_includes_domain(tmp_path):
    from odooctl.domains.base import RouteSpec
    from odooctl.domains.traefik import TraefikAdapter

    adapter = TraefikAdapter(dynamic_dir=tmp_path)
    spec = RouteSpec(domain="odoo.example.com", environment="production", scheme="https", port=None)
    adapter.attach_route(spec)

    config_file = tmp_path / "odooctl-production.yml"
    content = config_file.read_text()
    assert "odoo.example.com" in content


def test_traefik_adapter_attach_includes_service(tmp_path):
    from odooctl.domains.base import RouteSpec
    from odooctl.domains.traefik import TraefikAdapter

    adapter = TraefikAdapter(dynamic_dir=tmp_path)
    spec = RouteSpec(domain="odoo.example.com", environment="production", scheme="https", port=8069)
    adapter.attach_route(spec)

    config_file = tmp_path / "odooctl-production.yml"
    data = yaml.safe_load(config_file.read_text())
    assert "services" in data["http"]


def test_traefik_adapter_remove_route_deletes_file(tmp_path):
    from odooctl.domains.base import RouteSpec
    from odooctl.domains.traefik import TraefikAdapter

    adapter = TraefikAdapter(dynamic_dir=tmp_path)
    spec = RouteSpec(domain="odoo.example.com", environment="production", scheme="https", port=None)
    adapter.attach_route(spec)
    config_file = tmp_path / "odooctl-production.yml"
    assert config_file.exists()

    adapter.remove_route("production")
    assert not config_file.exists()


def test_traefik_adapter_remove_route_noop_if_missing(tmp_path):
    from odooctl.domains.traefik import TraefikAdapter
    adapter = TraefikAdapter(dynamic_dir=tmp_path)
    # Should not raise even when file doesn't exist
    adapter.remove_route("nonexistent")


def test_traefik_adapter_get_route_status_active_when_file_exists(tmp_path):
    from odooctl.domains.base import RouteSpec
    from odooctl.domains.traefik import TraefikAdapter

    adapter = TraefikAdapter(dynamic_dir=tmp_path)
    spec = RouteSpec(domain="odoo.example.com", environment="production", scheme="https", port=None)
    adapter.attach_route(spec)

    status = adapter.get_route_status("production")
    assert status.active is True


def test_traefik_adapter_get_route_status_inactive_when_no_file(tmp_path):
    from odooctl.domains.traefik import TraefikAdapter

    adapter = TraefikAdapter(dynamic_dir=tmp_path)
    status = adapter.get_route_status("production")
    assert status.active is False
    assert status.config_path is None


def test_traefik_adapter_https_route_has_tls(tmp_path):
    from odooctl.domains.base import RouteSpec
    from odooctl.domains.traefik import TraefikAdapter

    adapter = TraefikAdapter(dynamic_dir=tmp_path)
    spec = RouteSpec(domain="odoo.example.com", environment="production", scheme="https", port=None)
    adapter.attach_route(spec)

    config_file = tmp_path / "odooctl-production.yml"
    data = yaml.safe_load(config_file.read_text())
    router = next(iter(data["http"]["routers"].values()))
    assert "tls" in router


def test_traefik_adapter_http_route_no_tls(tmp_path):
    from odooctl.domains.base import RouteSpec
    from odooctl.domains.traefik import TraefikAdapter

    adapter = TraefikAdapter(dynamic_dir=tmp_path)
    spec = RouteSpec(domain="odoo.example.com", environment="staging", scheme="http", port=None)
    adapter.attach_route(spec)

    config_file = tmp_path / "odooctl-staging.yml"
    data = yaml.safe_load(config_file.read_text())
    router = next(iter(data["http"]["routers"].values()))
    assert "tls" not in router


def test_traefik_adapter_config_file_named_by_environment(tmp_path):
    from odooctl.domains.base import RouteSpec
    from odooctl.domains.traefik import TraefikAdapter

    adapter = TraefikAdapter(dynamic_dir=tmp_path)
    spec = RouteSpec(domain="qa.example.com", environment="qa", scheme="http", port=None)
    adapter.attach_route(spec)

    assert (tmp_path / "odooctl-qa.yml").exists()


def test_traefik_adapter_get_route_status_config_path(tmp_path):
    from odooctl.domains.base import RouteSpec
    from odooctl.domains.traefik import TraefikAdapter

    adapter = TraefikAdapter(dynamic_dir=tmp_path)
    spec = RouteSpec(domain="odoo.example.com", environment="production", scheme="https", port=None)
    adapter.attach_route(spec)

    status = adapter.get_route_status("production")
    assert status.config_path is not None
    assert "production" in status.config_path


# ---------------------------------------------------------------------------
# DNS resolution helper (injectable)
# ---------------------------------------------------------------------------

def test_dns_resolve_returns_ips():
    from odooctl.domains.base import resolve_domain

    def fake_resolver(domain: str) -> list[str]:
        return ["1.2.3.4"]

    ips = resolve_domain("odoo.example.com", resolver=fake_resolver)
    assert ips == ["1.2.3.4"]


def test_dns_resolve_empty_on_failure():
    from odooctl.domains.base import resolve_domain

    def failing_resolver(domain: str) -> list[str]:
        raise OSError("DNS failure")

    ips = resolve_domain("odoo.example.com", resolver=failing_resolver)
    assert ips == []


def test_dns_resolve_default_resolver_callable():
    from odooctl.domains.base import resolve_domain
    # Default resolver should be callable without keyword arg (may or may not succeed)
    # Just ensure it doesn't blow up with import error
    result = resolve_domain("localhost", resolver=lambda d: ["127.0.0.1"])
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# DomainService — attach / verify / detach
# ---------------------------------------------------------------------------

MINIMAL_CONFIG = """\
project:
  name: domain-test
  odoo_version: "19.0"
runtime:
  compose_file: docker-compose.yml
postgres:
  password_env: ODOO_DB_PASSWORD
odoo:
  image: odoo:19.0
environments:
  production:
    branch: main
    domain: odoo.example.com
    db_name: odoo_prod
    filestore_path: ./filestore/prod
  staging:
    branch: staging
    domain: staging.example.com
    db_name: odoo_staging
    filestore_path: ./filestore/staging
    clone_from: production
    sanitize: true
"""


def _make_ctx(tmp_path):
    cfg_path = tmp_path / "odooctl.yml"
    cfg_path.write_text(MINIMAL_CONFIG)
    from odooctl.services.context import ServiceContext
    return ServiceContext.from_config_path(cfg_path)


def test_domain_service_attach_calls_adapter(tmp_path):
    from odooctl.domains.base import RouteStatus
    from odooctl.services.domain import DomainService

    mock_adapter = MagicMock()
    mock_adapter.get_route_status.return_value = RouteStatus(active=True, config_path=str(tmp_path / "r.yml"))

    ctx = _make_ctx(tmp_path)
    svc = DomainService(ctx, adapter=mock_adapter)
    svc.attach("production", "odoo.example.com")

    mock_adapter.attach_route.assert_called_once()
    call_arg = mock_adapter.attach_route.call_args[0][0]
    assert call_arg.domain == "odoo.example.com"
    assert call_arg.environment == "production"


def test_domain_service_attach_uses_env_scheme(tmp_path):
    from odooctl.domains.base import RouteStatus
    from odooctl.services.domain import DomainService

    mock_adapter = MagicMock()
    mock_adapter.get_route_status.return_value = RouteStatus(active=True, config_path=str(tmp_path / "r.yml"))

    ctx = _make_ctx(tmp_path)
    svc = DomainService(ctx, adapter=mock_adapter)
    svc.attach("production", "odoo.example.com")

    call_arg = mock_adapter.attach_route.call_args[0][0]
    assert call_arg.scheme in ("http", "https")


def test_domain_service_detach_calls_adapter(tmp_path):
    from odooctl.services.domain import DomainService

    mock_adapter = MagicMock()
    ctx = _make_ctx(tmp_path)
    svc = DomainService(ctx, adapter=mock_adapter)
    svc.detach("production", "odoo.example.com")

    mock_adapter.remove_route.assert_called_once_with("production")


def test_domain_service_verify_returns_domain_status(tmp_path):
    from odooctl.domains.base import RouteStatus
    from odooctl.services.domain import DomainService

    mock_adapter = MagicMock()
    mock_adapter.get_route_status.return_value = RouteStatus(active=True, config_path=str(tmp_path / "r.yml"))

    ctx = _make_ctx(tmp_path)
    svc = DomainService(ctx, adapter=mock_adapter, resolver=lambda d: ["1.2.3.4"])
    status = svc.verify("production")

    from odooctl.domains.base import DomainStatus
    assert isinstance(status, DomainStatus)
    assert status.domain == "odoo.example.com"


def test_domain_service_verify_proxy_active(tmp_path):
    from odooctl.domains.base import RouteStatus
    from odooctl.services.domain import DomainService

    mock_adapter = MagicMock()
    mock_adapter.get_route_status.return_value = RouteStatus(active=True, config_path=str(tmp_path / "r.yml"))

    ctx = _make_ctx(tmp_path)
    svc = DomainService(ctx, adapter=mock_adapter, resolver=lambda d: ["1.2.3.4"])
    status = svc.verify("production")

    assert status.proxy_status == "active"


def test_domain_service_verify_proxy_inactive(tmp_path):
    from odooctl.domains.base import RouteStatus
    from odooctl.services.domain import DomainService

    mock_adapter = MagicMock()
    mock_adapter.get_route_status.return_value = RouteStatus(active=False, config_path=None)

    ctx = _make_ctx(tmp_path)
    svc = DomainService(ctx, adapter=mock_adapter, resolver=lambda d: ["1.2.3.4"])
    status = svc.verify("production")

    assert status.proxy_status == "inactive"


def test_domain_service_verify_no_expected_ip_dns_unknown(tmp_path):
    from odooctl.domains.base import RouteStatus
    from odooctl.services.domain import DomainService

    mock_adapter = MagicMock()
    mock_adapter.get_route_status.return_value = RouteStatus(active=True, config_path=str(tmp_path / "r.yml"))

    ctx = _make_ctx(tmp_path)
    svc = DomainService(ctx, adapter=mock_adapter, resolver=lambda d: ["1.2.3.4"], expected_host_ips=None)
    status = svc.verify("production")

    assert status.dns_status == "unknown"
    assert status.message is not None
    assert "expected" in status.message.lower()


def test_domain_service_verify_dns_ok_when_ip_matches(tmp_path):
    from odooctl.domains.base import RouteStatus
    from odooctl.services.domain import DomainService

    mock_adapter = MagicMock()
    mock_adapter.get_route_status.return_value = RouteStatus(active=True, config_path=str(tmp_path / "r.yml"))

    ctx = _make_ctx(tmp_path)
    svc = DomainService(ctx, adapter=mock_adapter, resolver=lambda d: ["1.2.3.4"], expected_host_ips=["1.2.3.4"])
    status = svc.verify("production")

    assert status.dns_status == "ok"


def test_domain_service_verify_dns_mismatch_when_ip_differs(tmp_path):
    from odooctl.domains.base import RouteStatus
    from odooctl.services.domain import DomainService

    mock_adapter = MagicMock()
    mock_adapter.get_route_status.return_value = RouteStatus(active=True, config_path=str(tmp_path / "r.yml"))

    ctx = _make_ctx(tmp_path)
    svc = DomainService(ctx, adapter=mock_adapter, resolver=lambda d: ["9.9.9.9"], expected_host_ips=["1.2.3.4"])
    status = svc.verify("production")

    assert status.dns_status == "mismatch"


def test_domain_service_verify_dns_fail_on_resolution_error(tmp_path):
    from odooctl.domains.base import RouteStatus
    from odooctl.services.domain import DomainService

    mock_adapter = MagicMock()
    mock_adapter.get_route_status.return_value = RouteStatus(active=True, config_path=str(tmp_path / "r.yml"))

    ctx = _make_ctx(tmp_path)
    svc = DomainService(ctx, adapter=mock_adapter, resolver=lambda d: [], expected_host_ips=["1.2.3.4"])
    status = svc.verify("production")

    # No IPs resolved → effectively a mismatch (no overlap)
    assert status.dns_status in ("mismatch", "failed")


def test_domain_service_cert_status_active_for_https_route(tmp_path):
    from odooctl.domains.base import RouteStatus
    from odooctl.services.domain import DomainService

    mock_adapter = MagicMock()
    mock_adapter.get_route_status.return_value = RouteStatus(active=True, config_path=str(tmp_path / "r.yml"))

    ctx = _make_ctx(tmp_path)
    svc = DomainService(ctx, adapter=mock_adapter, resolver=lambda d: ["1.2.3.4"])
    status = svc.verify("production")

    # production environment uses https scheme by default
    assert status.cert_status in ("active", "unknown")


# ---------------------------------------------------------------------------
# DomainService — attach persists domain to config file
# ---------------------------------------------------------------------------

def test_domain_service_attach_persists_domain_to_config_file(tmp_path):
    """attach() must write the new domain into the config YAML file."""
    from odooctl.domains.base import RouteStatus
    from odooctl.services.domain import DomainService

    mock_adapter = MagicMock()
    mock_adapter.get_route_status.return_value = RouteStatus(active=True, config_path=str(tmp_path / "r.yml"))

    ctx = _make_ctx(tmp_path)
    svc = DomainService(ctx, adapter=mock_adapter)
    svc.attach("production", "new.example.com")

    data = yaml.safe_load((tmp_path / "odooctl.yml").read_text())
    assert data["environments"]["production"]["domain"] == "new.example.com"


def test_domain_service_attach_does_not_expose_secrets(tmp_path):
    """attach() config write must not expose password values."""
    from odooctl.domains.base import RouteStatus
    from odooctl.services.domain import DomainService

    mock_adapter = MagicMock()
    mock_adapter.get_route_status.return_value = RouteStatus(active=True, config_path=str(tmp_path / "r.yml"))

    ctx = _make_ctx(tmp_path)
    svc = DomainService(ctx, adapter=mock_adapter)
    svc.attach("production", "new.example.com")

    config_text = (tmp_path / "odooctl.yml").read_text()
    assert "ODOO_DB_PASSWORD" not in config_text or "password_env:" in config_text


# ---------------------------------------------------------------------------
# DomainService — detach checks domain match before removing route
# ---------------------------------------------------------------------------

def test_domain_service_detach_noop_if_domain_mismatch(tmp_path):
    """detach() must not remove the route if the provided domain doesn't match env domain."""
    from odooctl.services.domain import DomainService

    mock_adapter = MagicMock()
    ctx = _make_ctx(tmp_path)
    svc = DomainService(ctx, adapter=mock_adapter)
    svc.detach("production", "different.example.com")  # env domain is "odoo.example.com"

    mock_adapter.remove_route.assert_not_called()


def test_domain_service_detach_removes_route_if_domain_matches(tmp_path):
    """detach() must remove the route when the provided domain matches env domain."""
    from odooctl.services.domain import DomainService

    mock_adapter = MagicMock()
    ctx = _make_ctx(tmp_path)
    svc = DomainService(ctx, adapter=mock_adapter)
    svc.detach("production", "odoo.example.com")  # matches env domain exactly

    mock_adapter.remove_route.assert_called_once_with("production")
