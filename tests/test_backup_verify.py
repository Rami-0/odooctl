"""M14 backup verify and restore-to-staging tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

import pytest


MINIMAL_CONFIG = """\
project:
  name: bv-test
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
    domain: odoo.example.com
    db_name: odoo_prod
    filestore_path: ./filestore/prod
  staging:
    branch: staging
    domain: staging.example.com
    db_name: odoo_staging
    filestore_path: ./filestore/staging
    clone_from: production
    sanitize: true
"""


def _make_valid_backup(backups_root: Path, environment: str, project: str = "bv-test") -> str:
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
    return backup_id


# ---------------------------------------------------------------------------
# Remote backup encryption metadata
# ---------------------------------------------------------------------------


def test_remote_encryption_metadata_records_algorithm_and_key_ref_only():
    from odooctl.config import BackupsConfig, OdooCtlConfig, RemoteBackupConfig
    from odooctl.services.backup import remote_encryption_metadata
    from odooctl.services.context import ServiceContext

    cfg = OdooCtlConfig.model_validate({
        "project": {"name": "bv-test", "odoo_version": "19.0"},
        "odoo": {"image": "odoo:19.0"},
        "environments": {
            "production": {
                "branch": "main",
                "domain": "odoo.example.com",
                "db_name": "odoo_prod",
                "filestore_path": "./filestore/prod",
            }
        },
        "backups": BackupsConfig(
            remote=RemoteBackupConfig(
                bucket="bucket",
                encryption_algorithm="aws:kms",
                encryption_key_env="ODOO_BACKUP_KMS_KEY_ID",
            )
        ).model_dump(),
    })
    ctx = cast(ServiceContext, SimpleNamespace(project=SimpleNamespace(config=cfg)))

    assert remote_encryption_metadata(ctx) == {
        "algorithm": "aws:kms",
        "key_ref": "env:ODOO_BACKUP_KMS_KEY_ID",
    }


def test_remote_backup_encryption_key_env_is_referenced_not_revealed():
    from odooctl.config import OdooCtlConfig

    cfg = OdooCtlConfig.model_validate({
        "project": {"name": "bv-test", "odoo_version": "19.0"},
        "odoo": {"image": "odoo:19.0"},
        "environments": {
            "production": {
                "branch": "main",
                "domain": "odoo.example.com",
                "db_name": "odoo_prod",
                "filestore_path": "./filestore/prod",
            }
        },
        "backups": {
            "remote": {
                "bucket": "bucket",
                "encryption_algorithm": "aws:kms",
                "encryption_key_env": "ODOO_BACKUP_KMS_KEY_ID",
            }
        },
    })

    assert "ODOO_BACKUP_KMS_KEY_ID" in cfg.referenced_env_vars()


# ---------------------------------------------------------------------------
# verify_backup — new helper in backup service
# ---------------------------------------------------------------------------

def test_verify_backup_ok_for_valid_backup(tmp_path):
    from odooctl.services.backup import verify_backup

    root = tmp_path / "backups"
    root.mkdir()
    backup_id = _make_valid_backup(root, "production")

    result = verify_backup(root, backup_id)
    assert result.ok is True
    assert result.backup_id == backup_id


def test_verify_backup_resolves_latest(tmp_path):
    from odooctl.services.backup import verify_backup

    root = tmp_path / "backups"
    root.mkdir()
    backup_id = _make_valid_backup(root, "production")

    result = verify_backup(root, "latest", environment="production")
    assert result.ok is True
    assert result.backup_id == backup_id


def test_verify_backup_fails_on_corrupt_db_dump(tmp_path):
    from odooctl.services.backup import verify_backup

    root = tmp_path / "backups"
    root.mkdir()
    backup_id = _make_valid_backup(root, "production")
    (root / backup_id / "db.dump").write_bytes(b"corrupt!")

    result = verify_backup(root, backup_id)
    assert result.ok is False
    assert result.error is not None
    assert "checksum" in result.error.lower()


def test_verify_backup_fails_on_missing_file(tmp_path):
    from odooctl.services.backup import verify_backup

    root = tmp_path / "backups"
    root.mkdir()
    backup_id = _make_valid_backup(root, "production")
    (root / backup_id / "filestore.tar").unlink()

    result = verify_backup(root, backup_id)
    assert result.ok is False


def test_verify_backup_result_has_backup_id_on_failure(tmp_path):
    from odooctl.services.backup import verify_backup

    root = tmp_path / "backups"
    root.mkdir()
    backup_id = _make_valid_backup(root, "production")
    (root / backup_id / "db.dump").write_bytes(b"corrupt!")

    result = verify_backup(root, backup_id)
    assert result.backup_id == backup_id


# ---------------------------------------------------------------------------
# restore_to_env — restore source-env backup into target env
# ---------------------------------------------------------------------------

def test_restore_to_env_refuses_production_as_target(tmp_path):
    from odooctl.services.restore import restore_to_env

    cfg_path = tmp_path / "odooctl.yml"
    cfg_path.write_text(MINIMAL_CONFIG)
    from odooctl.services.context import ServiceContext
    ctx = ServiceContext.from_config_path(cfg_path)

    with pytest.raises(RuntimeError, match="production"):
        restore_to_env(
            source_environment="production",
            target_environment="production",
            backup="latest",
            ctx=ctx,
        )


def test_restore_to_env_refuses_protected_target(tmp_path):
    from odooctl.services.restore import restore_to_env

    cfg_path = tmp_path / "odooctl.yml"
    cfg_path.write_text(MINIMAL_CONFIG)
    from odooctl.services.context import ServiceContext
    ctx = ServiceContext.from_config_path(cfg_path)

    # production is inherently protected
    with pytest.raises(RuntimeError):
        restore_to_env(
            source_environment="staging",
            target_environment="production",
            backup="latest",
            ctx=ctx,
        )


def test_restore_to_env_restores_to_target_db(tmp_path):
    from odooctl.services.restore import restore_to_env

    cfg_path = tmp_path / "odooctl.yml"
    cfg_path.write_text(MINIMAL_CONFIG)
    from odooctl.services.context import ServiceContext
    ctx = ServiceContext.from_config_path(cfg_path)

    # backups_dir resolves to ./backups relative to project root (tmp_path)
    backups_root = tmp_path / "backups"
    backups_root.mkdir()
    _make_valid_backup(backups_root, "production")

    mock_pg = MagicMock()
    mock_fs = MagicMock()

    with patch("odooctl.services.restore.PostgresAdapter", return_value=mock_pg), \
         patch("odooctl.services.restore.FilestoreAdapter", return_value=mock_fs), \
         patch("odooctl.services.restore.check_url"):
        restore_to_env(
            source_environment="production",
            target_environment="staging",
            backup="latest",
            ctx=ctx,
        )

    # Staging flow: restore goes into the temp DB (not the live target DB directly)
    mock_pg.restore.assert_called_once()
    db_name = mock_pg.restore.call_args[0][0]
    assert db_name == "odoo_staging_incoming"  # temp DB; swap promotes it into odoo_staging


def test_restore_to_env_returns_result_with_backup_id(tmp_path):
    from odooctl.services.restore import restore_to_env

    cfg_path = tmp_path / "odooctl.yml"
    cfg_path.write_text(MINIMAL_CONFIG)
    from odooctl.services.context import ServiceContext
    ctx = ServiceContext.from_config_path(cfg_path)

    # backups_dir resolves to ./backups relative to project root (tmp_path)
    backups_root = tmp_path / "backups"
    backups_root.mkdir()
    backup_id = _make_valid_backup(backups_root, "production")

    with patch("odooctl.services.restore.PostgresAdapter", return_value=MagicMock()), \
         patch("odooctl.services.restore.FilestoreAdapter", return_value=MagicMock()), \
         patch("odooctl.services.restore.check_url"):
        result = restore_to_env(
            source_environment="production",
            target_environment="staging",
            backup="latest",
            ctx=ctx,
        )

    assert result.backup_id == backup_id


def test_restore_to_env_restores_to_temp_db_first(tmp_path):
    """restore_to_env must restore into a temp DB, not directly into the target DB."""
    from odooctl.services.restore import restore_to_env

    cfg_path = tmp_path / "odooctl.yml"
    cfg_path.write_text(MINIMAL_CONFIG)
    from odooctl.services.context import ServiceContext
    ctx = ServiceContext.from_config_path(cfg_path)

    backups_root = tmp_path / "backups"
    backups_root.mkdir()
    _make_valid_backup(backups_root, "production")

    mock_pg = MagicMock()
    mock_fs = MagicMock()

    with patch("odooctl.services.restore.PostgresAdapter", return_value=mock_pg), \
         patch("odooctl.services.restore.FilestoreAdapter", return_value=mock_fs), \
         patch("odooctl.services.restore.check_url"):
        restore_to_env(
            source_environment="production",
            target_environment="staging",
            backup="latest",
            ctx=ctx,
        )

    mock_pg.restore.assert_called_once()
    db_name = mock_pg.restore.call_args[0][0]
    assert db_name != "odoo_staging", "restore must not go directly to target DB"
    assert "incoming" in db_name or db_name.endswith("_staging_incoming")


def test_restore_to_env_swap_called_before_healthcheck(tmp_path):
    """Swap (via psql rename) must happen after restore but before healthcheck."""
    from odooctl.services.restore import restore_to_env

    cfg_path = tmp_path / "odooctl.yml"
    cfg_path.write_text(MINIMAL_CONFIG)
    from odooctl.services.context import ServiceContext
    ctx = ServiceContext.from_config_path(cfg_path)

    backups_root = tmp_path / "backups"
    backups_root.mkdir()
    _make_valid_backup(backups_root, "production")

    call_order = []
    mock_pg = MagicMock()
    mock_pg.restore.side_effect = lambda *a, **kw: call_order.append("restore") or None
    mock_pg.psql.side_effect = lambda *a, **kw: call_order.append("psql") or None
    mock_fs = MagicMock()

    with patch("odooctl.services.restore.PostgresAdapter", return_value=mock_pg), \
         patch("odooctl.services.restore.FilestoreAdapter", return_value=mock_fs), \
         patch("odooctl.services.restore.check_url", lambda *a, **kw: call_order.append("healthcheck")):
        restore_to_env(
            source_environment="production",
            target_environment="staging",
            backup="latest",
            ctx=ctx,
        )

    assert "restore" in call_order
    assert "psql" in call_order, "swap_temp_database must call psql (terminate/drop/rename)"
    assert "healthcheck" in call_order
    ri = call_order.index("restore")
    si = call_order.index("psql")
    hi = call_order.index("healthcheck")
    assert ri < si < hi, f"Expected restore < swap < healthcheck, got {call_order}"


def test_restore_to_env_source_can_be_production(tmp_path):
    """Restore a production backup into staging — the canonical DR use case."""
    from odooctl.services.restore import restore_to_env

    cfg_path = tmp_path / "odooctl.yml"
    cfg_path.write_text(MINIMAL_CONFIG)
    from odooctl.services.context import ServiceContext
    ctx = ServiceContext.from_config_path(cfg_path)

    # backups_dir resolves to ./backups relative to project root (tmp_path)
    backups_root = tmp_path / "backups"
    backups_root.mkdir()
    _make_valid_backup(backups_root, "production")

    with patch("odooctl.services.restore.PostgresAdapter", return_value=MagicMock()), \
         patch("odooctl.services.restore.FilestoreAdapter", return_value=MagicMock()), \
         patch("odooctl.services.restore.check_url"):
        # Should not raise
        result = restore_to_env(
            source_environment="production",
            target_environment="staging",
            backup="latest",
            ctx=ctx,
        )
    assert result is not None
