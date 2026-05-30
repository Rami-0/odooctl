"""TDD tests for M7 ops CLI commands."""
from __future__ import annotations

import json

from typer.testing import CliRunner

MINIMAL_CONFIG = """\
project:
  name: demo
  odoo_version: "19.0"
runtime:
  compose_file: docker-compose.yml
postgres:
  host: localhost
  port: 5432
  user: odoo
  password_env: ODOO_DB_PASSWORD
backups:
  local_path: backups
healthcheck:
  path: /web/health
  timeout_seconds: 10
  retries: 3
  interval_seconds: 1
odoo:
  image: registry/odoo:latest
  service: odoo
environments:
  production:
    branch: main
    domain: odoo.example.com
    db_name: odoo_prod
    filestore_path: /srv/filestore/prod
  staging:
    branch: staging
    domain: staging.example.com
    db_name: odoo_staging
    filestore_path: /srv/filestore/staging
    clone_from: production
    sanitize: true
"""


def _make_config(tmp_path):
    config = tmp_path / "odooctl.yml"
    config.write_text(MINIMAL_CONFIG)
    return config


def _make_store_with_ops(tmp_path, count=2):
    from odooctl.operations.audit import AuditStore
    from odooctl.operations.engine import run_operation
    from odooctl.operations.models import OperationKind
    from odooctl.operations.store import OperationStore

    state_dir = tmp_path / ".odooctl"
    store = OperationStore(state_dir)
    audit = AuditStore(state_dir)
    ids = []
    for i in range(count):
        env = "staging" if i % 2 == 0 else "production"
        kind = OperationKind.BACKUP if i % 2 == 0 else OperationKind.DEPLOY
        with run_operation(
            store, audit,
            kind=kind, project="demo", environment=env,
            actor="cli", params_redacted={}, state_dir=state_dir,
        ) as op_ctx:
            op_ctx.emit(f"step {i}", phase="test")
            ids.append(op_ctx.op.id)
    return store, ids


def test_ops_list_empty_shows_table(tmp_path):
    from odooctl.main import app
    runner = CliRunner()
    config = _make_config(tmp_path)
    result = runner.invoke(app, ["ops", "list", "--config", str(config)])
    assert result.exit_code == 0


def test_ops_list_shows_operations(tmp_path):
    from odooctl.main import app
    runner = CliRunner()
    config = _make_config(tmp_path)
    _make_store_with_ops(tmp_path, count=2)
    result = runner.invoke(app, ["ops", "list", "--config", str(config)])
    assert result.exit_code == 0
    assert "backup" in result.output or "deploy" in result.output


def test_ops_list_json_output(tmp_path):
    from odooctl.main import app
    runner = CliRunner()
    config = _make_config(tmp_path)
    _make_store_with_ops(tmp_path, count=1)
    result = runner.invoke(app, ["ops", "list", "--json", "--config", str(config)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 1


def test_ops_show_found(tmp_path):
    from odooctl.main import app
    runner = CliRunner()
    config = _make_config(tmp_path)
    _, ids = _make_store_with_ops(tmp_path, count=1)
    result = runner.invoke(app, ["ops", "show", ids[0], "--config", str(config)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["id"] == ids[0]


def test_ops_show_not_found(tmp_path):
    from odooctl.main import app
    runner = CliRunner()
    config = _make_config(tmp_path)
    result = runner.invoke(app, ["ops", "show", "notexist", "--config", str(config)])
    assert result.exit_code != 0


def test_ops_logs_shows_events(tmp_path):
    from odooctl.main import app
    runner = CliRunner()
    config = _make_config(tmp_path)
    _, ids = _make_store_with_ops(tmp_path, count=1)
    result = runner.invoke(app, ["ops", "logs", ids[0], "--config", str(config)])
    assert result.exit_code == 0
    assert "step 0" in result.output


def test_ops_logs_not_found(tmp_path):
    from odooctl.main import app
    runner = CliRunner()
    config = _make_config(tmp_path)
    result = runner.invoke(app, ["ops", "logs", "badid", "--config", str(config)])
    assert result.exit_code != 0


def test_ops_cancel_sets_status_cancelled(tmp_path):
    from odooctl.main import app
    from odooctl.operations.store import OperationStore
    from odooctl.operations.models import Operation, OperationKind, OperationStatus
    runner = CliRunner()
    config = _make_config(tmp_path)
    state_dir = tmp_path / ".odooctl"
    store = OperationStore(state_dir)
    op = Operation.create(OperationKind.BACKUP, "demo", "staging", "cli", {})
    op.status = OperationStatus.RUNNING
    store.save(op)
    result = runner.invoke(app, ["ops", "cancel", op.id, "--config", str(config)])
    assert result.exit_code == 0
    loaded = store.load(op.id)
    assert loaded.status == OperationStatus.CANCELLED


def test_ops_cancel_refuses_succeeded_operation(tmp_path):
    from odooctl.main import app
    from odooctl.operations.models import Operation, OperationKind, OperationStatus
    from odooctl.operations.store import OperationStore
    runner = CliRunner()
    config = _make_config(tmp_path)
    state_dir = tmp_path / ".odooctl"
    store = OperationStore(state_dir)
    op = Operation.create(OperationKind.BACKUP, "demo", "staging", "cli", {})
    op.status = OperationStatus.SUCCEEDED
    store.save(op)
    result = runner.invoke(app, ["ops", "cancel", op.id, "--config", str(config)])
    assert result.exit_code != 0


def test_ops_cancel_not_found(tmp_path):
    from odooctl.main import app
    runner = CliRunner()
    config = _make_config(tmp_path)
    result = runner.invoke(app, ["ops", "cancel", "missing", "--config", str(config)])
    assert result.exit_code != 0


def test_ops_logs_follow_exits_on_completed_operation(tmp_path):
    """ops logs --follow should exit once the operation is in a terminal state."""
    from odooctl.main import app
    runner = CliRunner()
    config = _make_config(tmp_path)
    _, ids = _make_store_with_ops(tmp_path, count=1)
    # Already succeeded → --follow should return immediately
    result = runner.invoke(app, ["ops", "logs", ids[0], "--follow", "--config", str(config)])
    assert result.exit_code == 0
