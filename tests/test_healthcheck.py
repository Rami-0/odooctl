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
