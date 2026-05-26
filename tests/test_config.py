from pathlib import Path

import pytest

from odooctl.commands.backup import redact_config_snapshot
from odooctl.config import example_config, load_config


EXAMPLE_PATH = Path(__file__).resolve().parents[1] / "examples" / "odooctl.yml"
WORKFLOW_PATH = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "odooctl-deploy.yml"


def test_example_config_loads(tmp_path: Path):
    path = tmp_path / "odooctl.yml"
    path.write_text(example_config())
    cfg = load_config(path)
    assert cfg.project.name == "demo-odoo-project"
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


def test_missing_env_vars_reports_only_referenced_values(monkeypatch):
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")
    monkeypatch.setenv("ODOO_S3_ENDPOINT", "https://s3.example.com")
    cfg = load_config(EXAMPLE_PATH)
    assert cfg.referenced_env_vars() == ["ODOO_DB_PASSWORD", "ODOO_S3_ACCESS_KEY", "ODOO_S3_ENDPOINT", "ODOO_S3_SECRET_KEY"]
    assert cfg.missing_env_vars() == ["ODOO_S3_ACCESS_KEY", "ODOO_S3_SECRET_KEY"]


def test_environment_clone_from_must_reference_known_environment(tmp_path: Path):
    path = tmp_path / "odooctl.yml"
    path.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\nodoo:\n  image: registry/odoo:latest\n  service: odoo\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /srv/filestore/prod\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /srv/filestore/staging\n    clone_from: preview\n"""
    )

    with pytest.raises(ValueError) as exc_info:
        load_config(path)

    assert "clone_from 'preview' is not defined" in str(exc_info.value)


def test_environment_clone_from_can_be_omitted(tmp_path: Path):
    path = tmp_path / "odooctl.yml"
    path.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\nodoo:\n  image: registry/odoo:latest\n  service: odoo\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /srv/filestore/prod\n  qa:\n    branch: qa\n    domain: qa.example.com\n    db_name: odoo_qa\n    filestore_path: /srv/filestore/qa\n"""
    )

    cfg = load_config(path)

    assert cfg.env("production").clone_from is None
    assert cfg.env("qa").clone_from is None


def test_environment_clone_from_cannot_reference_itself(tmp_path: Path):
    path = tmp_path / "odooctl.yml"
    path.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\nodoo:\n  image: registry/odoo:latest\n  service: odoo\nenvironments:\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /srv/filestore/staging\n    clone_from: staging\n"""
    )

    with pytest.raises(ValueError) as exc_info:
        load_config(path)

    assert "cannot clone_from itself" in str(exc_info.value)


def test_production_cannot_be_a_clone_target(tmp_path: Path):
    path = tmp_path / "odooctl.yml"
    path.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\nodoo:\n  image: registry/odoo:latest\n  service: odoo\nenvironments:\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /srv/filestore/staging\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /srv/filestore/prod\n    clone_from: staging\n"""
    )

    with pytest.raises(ValueError) as exc_info:
        load_config(path)

    assert "Environment 'production' cannot be a clone target" in str(exc_info.value)


def test_environments_cannot_share_db_name(tmp_path: Path):
    path = tmp_path / "odooctl.yml"
    path.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\nodoo:\n  image: registry/odoo:latest\n  service: odoo\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_shared\n    filestore_path: /srv/filestore/prod\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_shared\n    filestore_path: /srv/filestore/staging\n    clone_from: production\n"""
    )

    with pytest.raises(ValueError) as exc_info:
        load_config(path)

    message = str(exc_info.value)
    assert "Environments 'production' and 'staging' cannot share db_name 'odoo_shared'" in message


def test_environments_cannot_share_filestore_path(tmp_path: Path):
    path = tmp_path / "odooctl.yml"
    path.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\nodoo:\n  image: registry/odoo:latest\n  service: odoo\nenvironments:\n  production:\n    branch: main\n    domain: odoo.example.com\n    db_name: odoo_prod\n    filestore_path: /srv/filestore/shared\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /srv/filestore/shared\n    clone_from: production\n"""
    )

    with pytest.raises(ValueError) as exc_info:
        load_config(path)

    message = str(exc_info.value)
    assert "Environments 'production' and 'staging' cannot share filestore_path '/srv/filestore/shared'" in message
