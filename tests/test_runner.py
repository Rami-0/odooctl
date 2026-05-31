"""M12 runner tests — queue, worker, token verification, nonce tracking."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from odooctl.api.queue import OperationQueue, QueueEntry
from odooctl.security import tokens

TEST_KEY = "test-runner-key-xyz"

MINIMAL_CONFIG = """\
project:
  name: test-project
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
    domain: prod.test.local
    port: 8069
    db_name: test_prod
    filestore_path: ./filestore/production
"""

MINIMAL_CONFIG_PROTECTED_STAGING = """\
project:
  name: test-project
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
    domain: prod.test.local
    port: 8069
    db_name: test_prod
    filestore_path: ./filestore/production
  secure_staging:
    branch: secure-staging
    domain: secure-staging.test.local
    port: 8070
    db_name: test_secure_staging
    filestore_path: ./filestore/secure_staging
    clone_from: production
    protected: true
"""


def _make_entry(
    op_id: str = "abc123",
    kind: str = "backup",
    project: str = "test-project",
    env: str = "production",
    nonce: str | None = None,
    roles: list[str] | None = None,
) -> QueueEntry:
    extra: dict = {"roles": roles if roles is not None else ["operator"]}
    token = tokens.mint(
        TEST_KEY,
        action=kind,
        environment=env,
        project=project,
        ttl_seconds=300,
        nonce=nonce,
        **extra,
    )
    return QueueEntry.create(
        op_id=op_id,
        kind=kind,
        project=project,
        environment=env,
        actor="api-client",
        params_redacted={},
        token=token,
    )


@pytest.fixture
def project_dir(tmp_path):
    (tmp_path / "odooctl.yml").write_text(MINIMAL_CONFIG)
    return tmp_path


@pytest.fixture
def fake_registry(project_dir):
    from odooctl.registry import Registry, RegisteredProject

    return Registry(
        path=project_dir / "registry.toml",
        active="test-project",
        projects={
            "test-project": RegisteredProject(
                name="test-project",
                path=project_dir,
                config="odooctl.yml",
            )
        },
    )


def _pre_create_op(project_dir: Path, op_id: str) -> None:
    from odooctl.operations.models import Operation, OperationKind
    from odooctl.operations.store import OperationStore

    store = OperationStore(project_dir / ".odooctl")
    op = Operation.create(OperationKind.BACKUP, "test-project", "production", "api-client", {})
    op.id = op_id
    store.save(op)


def _make_backup_result(project_dir: Path = None, backup_id: str = "bk001"):
    from odooctl.services.models import BackupResult

    return BackupResult(backup_id=backup_id)


# --- Queue tests ---


def test_queue_enqueue_creates_file(tmp_path):
    q = OperationQueue(tmp_path)
    entry = _make_entry()
    q.enqueue(entry)
    assert (tmp_path / "queue" / "abc123.json").exists()


def test_queue_claim_returns_entry(tmp_path):
    q = OperationQueue(tmp_path)
    q.enqueue(_make_entry())
    claimed = q.claim_next()
    assert claimed is not None
    assert claimed.op_id == "abc123"
    assert claimed.kind == "backup"


def test_queue_claim_atomic_rename(tmp_path):
    q = OperationQueue(tmp_path)
    q.enqueue(_make_entry())
    q.claim_next()
    assert not (tmp_path / "queue" / "abc123.json").exists()
    assert (tmp_path / "queue" / "abc123.running").exists()


def test_queue_claim_returns_none_when_empty(tmp_path):
    q = OperationQueue(tmp_path)
    assert q.claim_next() is None


def test_queue_complete_removes_file(tmp_path):
    q = OperationQueue(tmp_path)
    q.enqueue(_make_entry())
    q.claim_next()
    q.complete("abc123")
    assert not (tmp_path / "queue" / "abc123.running").exists()


def test_queue_fail_renames_to_failed(tmp_path):
    q = OperationQueue(tmp_path)
    q.enqueue(_make_entry())
    q.claim_next()
    q.fail("abc123")
    assert (tmp_path / "queue" / "abc123.failed").exists()
    assert not (tmp_path / "queue" / "abc123.running").exists()


def test_queue_entry_roundtrip(tmp_path):
    entry = _make_entry()
    q = OperationQueue(tmp_path)
    q.enqueue(entry)
    claimed = q.claim_next()
    assert claimed is not None
    assert claimed.op_id == entry.op_id
    assert claimed.kind == entry.kind
    assert claimed.token == entry.token


def test_queue_cancel_removes_json_file(tmp_path):
    """cancel() must remove the pending .json queue entry."""
    q = OperationQueue(tmp_path)
    q.enqueue(_make_entry())
    assert (tmp_path / "queue" / "abc123.json").exists()
    q.cancel("abc123")
    assert not (tmp_path / "queue" / "abc123.json").exists()


def test_queue_cancel_noop_if_already_claimed(tmp_path):
    """cancel() on a claimed (running) entry must not raise."""
    q = OperationQueue(tmp_path)
    q.enqueue(_make_entry())
    q.claim_next()
    q.cancel("abc123")
    assert (tmp_path / "queue" / "abc123.running").exists()


def test_queue_cancel_noop_if_already_gone(tmp_path):
    """cancel() on an already-absent entry must not raise."""
    q = OperationQueue(tmp_path)
    q.cancel("nonexistent")


def test_claim_next_skips_corrupt_json_entry(tmp_path):
    """claim_next() must tolerate corrupt JSON by moving the entry to .corrupt."""
    q = OperationQueue(tmp_path)
    (tmp_path / "queue" / "corrupt001.json").write_text("{invalid json}")
    result = q.claim_next()
    assert result is None
    assert not (tmp_path / "queue" / "corrupt001.json").exists()
    assert not (tmp_path / "queue" / "corrupt001.running").exists()
    assert (tmp_path / "queue" / "corrupt001.corrupt").exists()


def test_claim_next_skips_corrupt_entry_and_returns_valid(tmp_path):
    """claim_next() must skip corrupt entries and still return a valid one."""
    q = OperationQueue(tmp_path)
    import time as _time
    (tmp_path / "queue" / "bad000.json").write_text("!!not json!!")
    _time.sleep(0.01)  # ensure ordering
    q.enqueue(_make_entry(op_id="good001"))
    result = q.claim_next()
    assert result is not None
    assert result.op_id == "good001"


# --- Runner worker tests ---


def test_runner_claims_and_executes_backup(project_dir, fake_registry):
    from odooctl.operations.models import OperationStatus
    from odooctl.operations.store import OperationStore
    from odooctl.runner.worker import RunnerWorker

    op_id = "runner001"
    _pre_create_op(project_dir, op_id)
    entry = _make_entry(op_id=op_id)
    OperationQueue(project_dir / ".odooctl").enqueue(entry)

    worker = RunnerWorker(registry=fake_registry, api_key=TEST_KEY)
    with patch("odooctl.runner.worker.run_backup", return_value=_make_backup_result()):
        did_work = worker.claim_and_run()

    assert did_work is True
    store = OperationStore(project_dir / ".odooctl")
    assert store.load(op_id).status == OperationStatus.SUCCEEDED


def test_runner_rejects_tampered_token(project_dir, fake_registry):
    from odooctl.operations.models import OperationStatus
    from odooctl.operations.store import OperationStore
    from odooctl.runner.worker import RunnerWorker

    op_id = "runner002"
    _pre_create_op(project_dir, op_id)

    good = tokens.mint(TEST_KEY, action="backup", environment="production", project="test-project", ttl_seconds=300)
    tampered = good[:-5] + "XXXXX"
    entry = QueueEntry.create(
        op_id=op_id,
        kind="backup",
        project="test-project",
        environment="production",
        actor="api-client",
        params_redacted={},
        token=tampered,
    )
    OperationQueue(project_dir / ".odooctl").enqueue(entry)

    worker = RunnerWorker(registry=fake_registry, api_key=TEST_KEY)
    did_work = worker.claim_and_run()

    assert did_work is True
    store = OperationStore(project_dir / ".odooctl")
    assert store.load(op_id).status == OperationStatus.FAILED


def test_runner_records_nonce_as_consumed(project_dir, fake_registry):
    from odooctl.runner.worker import NonceStore, RunnerWorker

    op_id = "runner003"
    _pre_create_op(project_dir, op_id)
    entry = _make_entry(op_id=op_id)
    OperationQueue(project_dir / ".odooctl").enqueue(entry)

    worker = RunnerWorker(registry=fake_registry, api_key=TEST_KEY)
    with patch("odooctl.runner.worker.run_backup", return_value=_make_backup_result(backup_id="bk003")):
        worker.claim_and_run()

    nonce = tokens.decode_unverified(entry.token)["nonce"]
    assert NonceStore(project_dir / ".odooctl").is_consumed(nonce)


def test_runner_rejects_replayed_nonce(project_dir, fake_registry):
    from odooctl.operations.models import OperationStatus
    from odooctl.operations.store import OperationStore
    from odooctl.runner.worker import NonceStore, RunnerWorker

    nonce = "premarked_nonce_xyz"
    NonceStore(project_dir / ".odooctl").mark_consumed(nonce)

    op_id = "runner004"
    _pre_create_op(project_dir, op_id)
    entry = _make_entry(op_id=op_id, nonce=nonce)
    OperationQueue(project_dir / ".odooctl").enqueue(entry)

    worker = RunnerWorker(registry=fake_registry, api_key=TEST_KEY)
    did_work = worker.claim_and_run()

    assert did_work is True
    store = OperationStore(project_dir / ".odooctl")
    op = store.load(op_id)
    assert op.status == OperationStatus.FAILED
    assert "nonce" in (op.error or "")


def test_runner_returns_false_when_queue_empty(project_dir, fake_registry):
    from odooctl.runner.worker import RunnerWorker

    worker = RunnerWorker(registry=fake_registry, api_key=TEST_KEY)
    assert worker.claim_and_run() is False


def test_runner_marks_operation_failed_on_service_error(project_dir, fake_registry):
    from odooctl.operations.models import OperationStatus
    from odooctl.operations.store import OperationStore
    from odooctl.runner.worker import RunnerWorker

    op_id = "runner_fail"
    _pre_create_op(project_dir, op_id)
    entry = _make_entry(op_id=op_id)
    OperationQueue(project_dir / ".odooctl").enqueue(entry)

    worker = RunnerWorker(registry=fake_registry, api_key=TEST_KEY)
    with patch("odooctl.runner.worker.run_backup", side_effect=RuntimeError("disk full")):
        did_work = worker.claim_and_run()

    assert did_work is True
    store = OperationStore(project_dir / ".odooctl")
    op = store.load(op_id)
    assert op.status == OperationStatus.FAILED
    assert "disk full" in (op.error or "")


def test_runner_skips_cancelled_operation_after_claim(project_dir, fake_registry):
    """Runner must skip execution when operation status is CANCELLED (post-claim race)."""
    from odooctl.operations.models import OperationStatus
    from odooctl.operations.store import OperationStore
    from odooctl.runner.worker import RunnerWorker

    op_id = "cancel001"
    _pre_create_op(project_dir, op_id)

    store = OperationStore(project_dir / ".odooctl")
    store.update_status(op_id, OperationStatus.CANCELLED)

    entry = _make_entry(op_id=op_id)
    OperationQueue(project_dir / ".odooctl").enqueue(entry)

    call_count = []

    def mock_backup(*a, **kw):
        call_count.append(1)
        return _make_backup_result()

    worker = RunnerWorker(registry=fake_registry, api_key=TEST_KEY)
    with patch("odooctl.runner.worker.run_backup", side_effect=mock_backup):
        did_work = worker.claim_and_run()

    assert did_work is True
    assert not call_count
    assert store.load(op_id).status == OperationStatus.CANCELLED


def test_runner_rejects_protected_destructive_op_with_operator_role(tmp_path):
    """Runner must reject a destructive op on a protected env when token has operator-level roles.

    Simulates a malformed/forged queue entry where operator roles are embedded
    in the capability token but the target is an explicitly protected environment.
    Clone to secure_staging (protected=true) with operator roles must fail with
    an RBAC error, not reach dispatch.
    """
    from odooctl.operations.models import Operation, OperationKind, OperationStatus
    from odooctl.operations.store import OperationStore
    from odooctl.registry import RegisteredProject, Registry
    from odooctl.runner.worker import RunnerWorker

    (tmp_path / "odooctl.yml").write_text(MINIMAL_CONFIG_PROTECTED_STAGING)
    registry = Registry(
        path=tmp_path / "registry.toml",
        active="test-project",
        projects={"test-project": RegisteredProject("test-project", tmp_path, "odooctl.yml")},
    )

    store = OperationStore(tmp_path / ".odooctl")
    op_id = "rbac_prot_001"
    op = Operation.create(OperationKind.CLONE, "test-project", "secure_staging", "op-user", {})
    op.id = op_id
    store.save(op)

    # Capability token carries operator roles — not sufficient for a protected env clone
    entry = _make_entry(op_id=op_id, kind="clone", env="secure_staging", roles=["operator"])
    OperationQueue(tmp_path / ".odooctl").enqueue(entry)

    worker = RunnerWorker(registry=registry, api_key=TEST_KEY)
    did_work = worker.claim_and_run()

    assert did_work is True
    op = store.load(op_id)
    assert op.status == OperationStatus.FAILED
    assert "protected" in (op.error or "").lower()


def test_runner_once_processes_one_item(project_dir, fake_registry):
    from odooctl.runner.worker import RunnerWorker

    call_count = 0

    def mock_backup(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return _make_backup_result(backup_id=f"bk_{call_count}")

    # Enqueue 2 items
    for i in range(2):
        op_id = f"once{i:03d}"
        _pre_create_op(project_dir, op_id)
        OperationQueue(project_dir / ".odooctl").enqueue(_make_entry(op_id=op_id))

    worker = RunnerWorker(registry=fake_registry, api_key=TEST_KEY)
    with patch("odooctl.runner.worker.run_backup", side_effect=mock_backup):
        worker.run_loop(once=True)

    assert call_count == 1
