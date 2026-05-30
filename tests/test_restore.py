import json
from pathlib import Path

import pytest

from odooctl.commands.restore import execute, resolve_backup_dir, sha256_file, validate_backup_dir


def write_manifest(path: Path, *, project: str = "p", environment: str = "staging") -> None:
    backup = path.parent
    path.write_text(
        json.dumps(
            {
                "project": project,
                "environment": environment,
                "backup_id": backup.name,
                "schema_version": 1,
                "backup_mode": "full",
                "db_name": "odoo_staging",
                "filestore_path": "/var/lib/odoo/filestore/odoo_staging",
                "odoo_version": "19.0",
                "checksums": {
                    "db_dump": sha256_file(backup / "db.dump"),
                    "filestore": sha256_file(backup / "filestore.tar"),
                },
            }
        )
    )


def make_backup(root: Path, name: str, *, project: str = "p") -> Path:
    backup = root / name
    backup.mkdir(parents=True)
    (backup / "db.dump").write_bytes(b"db")
    (backup / "filestore.tar").write_bytes(b"fs")
    write_manifest(backup / "manifest.json", project=project)
    return backup


def test_latest_restore_uses_requested_environment(tmp_path: Path):
    make_backup(tmp_path, "production_2026-01-01_000000")
    staging = make_backup(tmp_path, "staging_2026-01-02_000000")
    assert resolve_backup_dir("staging", "latest", tmp_path) == staging


def test_restore_preflight_requires_backup_directory(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        validate_backup_dir(tmp_path / "missing", expected_project="p")


def test_restore_preflight_requires_db_dump_before_destructive_restore(tmp_path: Path):
    backup = make_backup(tmp_path, "staging_1")
    (backup / "db.dump").unlink()
    with pytest.raises(FileNotFoundError, match="db.dump"):
        validate_backup_dir(backup, expected_project="p")


def test_restore_preflight_requires_filestore_before_destructive_restore(tmp_path: Path):
    backup = make_backup(tmp_path, "staging_1")
    (backup / "filestore.tar").unlink()
    with pytest.raises(FileNotFoundError, match="filestore.tar"):
        validate_backup_dir(backup, expected_project="p")


def test_restore_preflight_rejects_wrong_project(tmp_path: Path):
    backup = make_backup(tmp_path, "staging_1", project="other")
    with pytest.raises(RuntimeError, match="Backup project mismatch"):
        validate_backup_dir(backup, expected_project="p")


def test_restore_preflight_rejects_wrong_environment(tmp_path: Path):
    backup = make_backup(tmp_path, "staging_1", project="p")
    with pytest.raises(RuntimeError, match="Backup environment mismatch"):
        validate_backup_dir(backup, expected_project="p", expected_environment="production")


def test_restore_preflight_rejects_unsupported_mode(tmp_path: Path):
    backup = make_backup(tmp_path, "staging_1", project="p")
    manifest = json.loads((backup / "manifest.json").read_text())
    manifest["backup_mode"] = "db-only"
    (backup / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match="Unsupported backup mode"):
        validate_backup_dir(backup, expected_project="p", expected_environment="staging", restore_mode="full")


def test_restore_preflight_rejects_missing_checksums(tmp_path: Path):
    backup = make_backup(tmp_path, "staging_1")
    manifest = json.loads((backup / "manifest.json").read_text())
    manifest.pop("checksums")
    (backup / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match="missing checksum"):
        validate_backup_dir(backup, expected_project="p")


def test_restore_preflight_rejects_checksum_mismatch(tmp_path: Path):
    backup = make_backup(tmp_path, "staging_1")
    manifest = json.loads((backup / "manifest.json").read_text())
    manifest["checksums"] = {"db_dump": "bad", "filestore": "bad"}
    (backup / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        validate_backup_dir(backup, expected_project="p")


def test_restore_reports_backup_name_after_successful_restore(tmp_path: Path, monkeypatch):
    config = tmp_path / "odooctl.yml"
    config.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\nbackups:\n  local_path: backups\nhealthcheck:\n  path: /web/health\n  timeout_seconds: 10\n  retries: 3\n  interval_seconds: 1\npostgres:\n  host: localhost\n  port: 5432\n  user: odoo\n  password_env: ODOO_DB_PASSWORD\nenvironments:\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: /var/lib/odoo/filestore/odoo_staging\nodoo:\n  image: registry/odoo:latest\n"""
    )
    backup = make_backup(tmp_path / "backups", "staging_2026-01-02_000000", project="demo")

    events: list[tuple[str, tuple[object, ...]]] = []

    class DummyPostgres:
        def __init__(self, config):
            events.append(("postgres_init", (config.host, config.port, config.user)))

        def restore(self, db_name, dump_path):
            events.append(("restore", (db_name, Path(dump_path).name)))

    class DummyFilestore:
        def restore_archive(self, archive_path, target_path):
            events.append(("filestore_restore", (Path(archive_path).name, target_path)))

    monkeypatch.setattr("odooctl.services.restore.PostgresAdapter", DummyPostgres)
    monkeypatch.setattr("odooctl.services.restore.FilestoreAdapter", DummyFilestore)
    monkeypatch.setattr("odooctl.services.restore.check_url", lambda *args, **kwargs: events.append(("healthcheck", args)))
    monkeypatch.chdir(tmp_path)

    assert execute("staging", backup.name, str(config)) == backup.name
    assert events[0] == ("postgres_init", ("localhost", 5432, "odoo"))
    assert events[1] == ("restore", ("odoo_staging", "db.dump"))
    assert events[2] == ("filestore_restore", ("filestore.tar", "/var/lib/odoo/filestore/odoo_staging"))
    assert events[3][0] == "healthcheck"
