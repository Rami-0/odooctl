from odooctl.utils.shell import join_csv, redact

def test_join_csv_strips_empty_values():
    assert join_csv([" sale", "", "stock "]) == "sale,stock"

def test_redact_masks_sensitive_environment_values():
    env = {"ODOO_DB_PASSWORD": "supersecret", "NORMAL": "visible"}
    assert redact("password=supersecret normal=visible", env) == "password=***REDACTED*** normal=visible"
