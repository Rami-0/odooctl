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
