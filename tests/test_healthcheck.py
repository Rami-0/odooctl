from odooctl.odoo import healthcheck


def test_healthcheck_rejects_404(monkeypatch):
    class FakeResponse:
        status = 404

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(healthcheck, "urlopen", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(healthcheck.time, "sleep", lambda interval: None)

    try:
        healthcheck.check_url("https://example.invalid", retries=1, interval=0)
    except RuntimeError as exc:
        assert "unexpected HTTP status 404" in str(exc)
    else:
        raise AssertionError("404 health check should fail")


def test_healthcheck_rejects_redirects(monkeypatch):
    from urllib.error import HTTPError

    def fake_urlopen(*args, **kwargs):
        raise HTTPError("https://example.invalid", 302, "Found", {}, None)

    monkeypatch.setattr(healthcheck, "urlopen", fake_urlopen)
    monkeypatch.setattr(healthcheck.time, "sleep", lambda interval: None)
    try:
        healthcheck.check_url("https://example.invalid", retries=1, interval=0)
    except RuntimeError as exc:
        assert "redirect" in str(exc)
    else:
        raise AssertionError("3xx health check should fail")


def test_healthcheck_requires_2xx(monkeypatch):
    class FakeResponse:
        status = 301

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(healthcheck, "urlopen", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(healthcheck.time, "sleep", lambda interval: None)
    try:
        healthcheck.check_url("https://example.invalid", retries=1, interval=0)
    except RuntimeError:
        pass
    else:
        raise AssertionError("non-2xx health check should fail")


def test_healthcheck_opener_does_not_follow_redirects():
    handler = healthcheck._NoRedirectHandler()
    assert handler.redirect_request(None, None, 302, "Found", {}, "https://x") is None
