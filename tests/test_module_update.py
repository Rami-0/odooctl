from odooctl.odoo import module_update

def test_update_modules_noops_without_modules(monkeypatch):
    called = False
    def fake_run(*args, **kwargs):
        nonlocal called
        called = True
    monkeypatch.setattr(module_update, "run", fake_run)
    module_update.update_modules_local("db", [])
    assert called is False

def test_update_modules_invokes_odoo_stop_after_init(monkeypatch):
    seen = {}
    def fake_run(args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
    monkeypatch.setattr(module_update, "run", fake_run)
    module_update.update_modules_local("db", ["sale", "stock"])
    assert seen["args"] == ["odoo", "-d", "db", "-u", "sale,stock", "--stop-after-init"]
    assert seen["kwargs"]["stream"] is True


def test_update_modules_compose_passes_odoo_db_flags(monkeypatch):
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")
    seen = {}

    class Compose:
        def exec(self, service, args, **kwargs):
            seen["service"] = service
            seen["args"] = args
            seen["kwargs"] = kwargs

    module_update.update_modules_compose(
        Compose(),
        "odoo",
        "odoo_prod",
        ["base"],
        db_host="db",
        db_user="odoo",
        db_password_env="ODOO_DB_PASSWORD",
        config_path="/etc/odoo/odoo.conf",
    )

    assert seen["service"] == "odoo"
    assert seen["args"] == [
        "odoo",
        "-d",
        "odoo_prod",
        "-u",
        "base",
        "--stop-after-init",
        "-c",
        "/etc/odoo/odoo.conf",
        "--db_host",
        "db",
        "--db_user",
        "odoo",
        "--db_password",
        "secret",
    ]
    assert seen["kwargs"]["stream"] is True


def test_update_modules_compose_requires_configured_password_env(monkeypatch):
    monkeypatch.delenv("ODOO_DB_PASSWORD", raising=False)

    class Compose:
        def exec(self, *args, **kwargs):  # pragma: no cover - should not be called
            raise AssertionError("exec should not be called")

    try:
        module_update.update_modules_compose(
            Compose(),
            "odoo",
            "odoo_prod",
            ["base"],
            db_host="db",
            db_user="odoo",
            db_password_env="ODOO_DB_PASSWORD",
        )
    except RuntimeError as exc:
        assert "ODOO_DB_PASSWORD" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError")
