from pathlib import Path

from odooctl.commands.backup import redact_config_snapshot
from odooctl.config import example_config, load_config


EXAMPLE_PATH = Path(__file__).resolve().parents[1] / "examples" / "odooctl.yml"
WORKFLOW_PATH = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "odooctl-deploy.yml"


def test_example_config_loads(tmp_path: Path):
    path = tmp_path / "odooctl.yml"
    path.write_text(example_config())
    cfg = load_config(path)
    assert cfg.project.name == "my-odoo-project"
    assert cfg.env("staging").sanitize is True
    assert cfg.postgres.password_env == "ODOO_DB_PASSWORD"


def test_config_uses_env_reference_not_secret_value():
    text = example_config()
    assert "password_env: ODOO_DB_PASSWORD" in text
    assert "password:" not in text


def test_example_file_matches_generated_config():
    assert EXAMPLE_PATH.read_text() == example_config()


def test_workflow_example_contains_deploy_command():
    workflow = WORKFLOW_PATH.read_text()
    assert "workflow_dispatch" in workflow
    assert "odooctl deploy ${{ inputs.environment }} --branch ${{ inputs.branch }}" in workflow
    assert "actions/setup-python@v5" in workflow


def test_redact_config_snapshot_masks_sensitive_values():
    raw = "admin_passwd = admin-secret\ndb_password = db-secret\nxmlrpc_port = 8069\n"
    redacted = redact_config_snapshot(raw)
    assert "admin-secret" not in redacted
    assert "db-secret" not in redacted
    assert "admin_passwd = ***REDACTED***" in redacted
    assert "xmlrpc_port = 8069" in redacted
