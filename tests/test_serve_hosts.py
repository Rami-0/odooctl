"""Tests for `odooctl serve` trusted-host allowlist (--allowed-host / ODOOCTL_ALLOWED_HOSTS).

The API is localhost-only by default; these cover the opt-in widening that lets it
be reached by IP/hostname without a reverse proxy, without ever removing localhost.
"""
from __future__ import annotations

import pytest

from odooctl.commands.serve import _split_hosts, resolve_allowed_hosts

TEST_KEY = "test-serve-hosts-secret-key-0123456789abcdef"


def test_split_hosts_handles_comma_space_and_empties():
    assert _split_hosts("a.example, b.example c.example") == ["a.example", "b.example", "c.example"]
    assert _split_hosts("") == []
    assert _split_hosts(None) == []
    assert _split_hosts(" , ,x, ") == ["x"]


def test_resolve_merges_cli_and_env_deduped_preserving_order():
    assert resolve_allowed_hosts(["10.0.0.1"], "10.0.0.2,10.0.0.1") == ["10.0.0.1", "10.0.0.2"]
    assert resolve_allowed_hosts(None, None) == []
    assert resolve_allowed_hosts(["*"], None) == ["*"]


def test_resolve_strips_whitespace_and_drops_blanks():
    assert resolve_allowed_hosts(["  host.a  ", ""], "  host.b ") == ["host.a", "host.b"]


# --- End-to-end: the extra host is actually admitted by TrustedHostMiddleware ---

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from odooctl.api.app import create_app  # noqa: E402


def _client(extra):
    app = create_app(api_key=TEST_KEY, extra_allowed_hosts=extra)
    return TestClient(app)


def test_unknown_host_is_rejected_by_default():
    # No extra hosts: a non-localhost Host header is refused before auth (400),
    # not passed through to a 401.
    client = _client(None)
    resp = client.get("/projects", headers={"Host": "203.0.113.9"})
    assert resp.status_code == 400  # "Invalid host header"


def test_extra_host_is_admitted_then_hits_auth():
    # With the host allowlisted it clears TrustedHost and reaches auth (401 for
    # a missing token) rather than being rejected as an invalid host (400).
    client = _client(["203.0.113.9"])
    resp = client.get("/projects", headers={"Host": "203.0.113.9"})
    assert resp.status_code == 401


def test_localhost_still_trusted_when_extra_hosts_added():
    client = _client(["203.0.113.9"])
    resp = client.get("/projects", headers={"Host": "localhost"})
    assert resp.status_code == 401  # trusted host, just unauthenticated


def test_wildcard_admits_any_host():
    client = _client(["*"])
    resp = client.get("/projects", headers={"Host": "anything.example.com"})
    assert resp.status_code == 401
