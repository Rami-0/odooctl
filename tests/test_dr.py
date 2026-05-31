"""M14 DR drill tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _make_backup(backups_root: Path, environment: str, project: str = "dr-test") -> Path:
    ts = "2026-05-31_100000"
    backup_id = f"{environment}_{ts}"
    d = backups_root / backup_id
    d.mkdir(parents=True)
    (d / "db.dump").write_bytes(b"dbdata")
    (d / "filestore.tar").write_bytes(b"fsdata")
    db_hash = hashlib.sha256(b"dbdata").hexdigest()
    fs_hash = hashlib.sha256(b"fsdata").hexdigest()
    manifest = {
        "backup_id": backup_id,
        "project": project,
        "environment": environment,
        "timestamp": ts,
        "db_name": f"{environment}_db",
        "odoo_version": "19.0",
        "backup_mode": "full",
        "checksums": {"db_dump": db_hash, "filestore": fs_hash},
    }
    (d / "manifest.json").write_text(json.dumps(manifest))
    return d


# ---------------------------------------------------------------------------
# DrDrillResult shape
# ---------------------------------------------------------------------------

def test_dr_drill_result_fields():
    from odooctl.services.dr import DrDrillResult
    r = DrDrillResult(
        status="success",
        environment="production",
        backup_id="production_2026-05-31_100000",
        message=None,
    )
    assert r.status == "success"
    assert r.environment == "production"
    assert r.backup_id is not None


# ---------------------------------------------------------------------------
# Protected environment check
# ---------------------------------------------------------------------------

def test_dr_drill_allows_protected_source_environment(tmp_path):
    """Protected environments (e.g. production) are valid DR drill SOURCES."""
    from odooctl.services.dr import run_dr_drill

    backups_root = tmp_path / "backups"
    backups_root.mkdir()
    _make_backup(backups_root, "production")

    result = run_dr_drill(
        environment="production",
        backups_root=backups_root,
        db_adapter=MagicMock(),
        fs_adapter=MagicMock(),
        healthcheck_fn=lambda url: True,
        is_protected_fn=lambda env: True,  # source is protected — must NOT block the drill
        throwaway_db_suffix="_dr_drill",
    )
    assert result.status == "success"


def test_dr_drill_raises_if_throwaway_matches_live_db(tmp_path):
    """Safety guard: throwaway DB name must differ from manifest live DB name."""
    from odooctl.services.dr import run_dr_drill

    backups_root = tmp_path / "backups"
    backups_root.mkdir()
    _make_backup(backups_root, "production")

    with pytest.raises(RuntimeError, match="throwaway"):
        run_dr_drill(
            environment="production",
            backups_root=backups_root,
            db_adapter=MagicMock(),
            fs_adapter=MagicMock(),
            healthcheck_fn=lambda url: True,
            is_protected_fn=lambda env: False,
            throwaway_db_suffix="",  # empty suffix → throwaway_db == live DB name
        )


def test_dr_drill_allows_non_protected_env(tmp_path):
    from odooctl.services.dr import run_dr_drill

    backups_root = tmp_path / "backups"
    backups_root.mkdir()
    _make_backup(backups_root, "production")

    mock_db = MagicMock()
    mock_fs = MagicMock()

    # should not raise
    result = run_dr_drill(
        environment="production",
        backups_root=backups_root,
        db_adapter=mock_db,
        fs_adapter=mock_fs,
        healthcheck_fn=lambda url: True,
        is_protected_fn=lambda env: False,  # nothing protected
        throwaway_db_suffix="_dr_drill",
    )
    assert result is not None


# ---------------------------------------------------------------------------
# Throwaway DB — restoration and cleanup
# ---------------------------------------------------------------------------

def test_dr_drill_restores_to_throwaway_db(tmp_path):
    from odooctl.services.dr import run_dr_drill

    backups_root = tmp_path / "backups"
    backups_root.mkdir()
    _make_backup(backups_root, "production")

    mock_db = MagicMock()
    mock_fs = MagicMock()

    run_dr_drill(
        environment="production",
        backups_root=backups_root,
        db_adapter=mock_db,
        fs_adapter=mock_fs,
        healthcheck_fn=lambda url: True,
        is_protected_fn=lambda env: False,
        throwaway_db_suffix="_dr_drill",
    )

    # DB restore must have been called
    mock_db.restore.assert_called_once()
    db_name_used = mock_db.restore.call_args[0][0]
    # Must not be the original production DB name from the manifest
    assert db_name_used != "production_db"
    assert "_dr_drill" in db_name_used or "drill" in db_name_used


def test_dr_drill_drops_throwaway_db_after_success(tmp_path):
    from odooctl.services.dr import run_dr_drill

    backups_root = tmp_path / "backups"
    backups_root.mkdir()
    _make_backup(backups_root, "production")

    mock_db = MagicMock()
    mock_fs = MagicMock()

    run_dr_drill(
        environment="production",
        backups_root=backups_root,
        db_adapter=mock_db,
        fs_adapter=mock_fs,
        healthcheck_fn=lambda url: True,
        is_protected_fn=lambda env: False,
        throwaway_db_suffix="_dr_drill",
    )

    mock_db.drop.assert_called_once()


def test_dr_drill_drops_throwaway_db_on_healthcheck_failure(tmp_path):
    from odooctl.services.dr import run_dr_drill

    backups_root = tmp_path / "backups"
    backups_root.mkdir()
    _make_backup(backups_root, "production")

    mock_db = MagicMock()
    mock_fs = MagicMock()

    result = run_dr_drill(
        environment="production",
        backups_root=backups_root,
        db_adapter=mock_db,
        fs_adapter=mock_fs,
        healthcheck_fn=lambda url: False,
        is_protected_fn=lambda env: False,
        throwaway_db_suffix="_dr_drill",
    )

    assert result.status == "failed"
    # Cleanup must still happen
    mock_db.drop.assert_called_once()


def test_dr_drill_drops_throwaway_db_on_restore_exception(tmp_path):
    from odooctl.services.dr import run_dr_drill

    backups_root = tmp_path / "backups"
    backups_root.mkdir()
    _make_backup(backups_root, "production")

    mock_db = MagicMock()
    mock_db.restore.side_effect = RuntimeError("restore failed")
    mock_fs = MagicMock()

    result = run_dr_drill(
        environment="production",
        backups_root=backups_root,
        db_adapter=mock_db,
        fs_adapter=mock_fs,
        healthcheck_fn=lambda url: True,
        is_protected_fn=lambda env: False,
        throwaway_db_suffix="_dr_drill",
    )

    assert result.status == "failed"
    # Drop should still be attempted for cleanup
    mock_db.drop.assert_called_once()


# ---------------------------------------------------------------------------
# Result fields
# ---------------------------------------------------------------------------

def test_dr_drill_success_result(tmp_path):
    from odooctl.services.dr import run_dr_drill

    backups_root = tmp_path / "backups"
    backups_root.mkdir()
    _make_backup(backups_root, "production")

    result = run_dr_drill(
        environment="production",
        backups_root=backups_root,
        db_adapter=MagicMock(),
        fs_adapter=MagicMock(),
        healthcheck_fn=lambda url: True,
        is_protected_fn=lambda env: False,
        throwaway_db_suffix="_dr_drill",
    )

    assert result.status == "success"
    assert result.backup_id is not None
    assert result.environment == "production"


def test_dr_drill_no_backup_raises(tmp_path):
    from odooctl.services.dr import run_dr_drill

    backups_root = tmp_path / "backups"
    backups_root.mkdir()

    with pytest.raises(RuntimeError, match="No backups found"):
        run_dr_drill(
            environment="production",
            backups_root=backups_root,
            db_adapter=MagicMock(),
            fs_adapter=MagicMock(),
            healthcheck_fn=lambda url: True,
            is_protected_fn=lambda env: False,
        )
