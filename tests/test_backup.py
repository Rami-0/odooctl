from __future__ import annotations

import os

from odooctl.adapters.s3 import S3Adapter
from odooctl.commands.backup import prune_backups
from odooctl.config import RemoteBackupConfig


def test_prune_backups_keeps_most_recent(tmp_path):
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    for index in range(4):
        path = backup_root / f"backup_{index}"
        path.mkdir()
        (path / "marker.txt").write_text(str(index))
        os.utime(path, (100 + index, 100 + index))

    removed = prune_backups(backup_root, keep=2)

    assert {p.name for p in removed} == {"backup_0", "backup_1"}
    assert sorted(p.name for p in backup_root.iterdir()) == ["backup_2", "backup_3"]


def test_prune_backups_keeps_most_recent_per_environment(tmp_path):
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    for index, name in enumerate(["production_1", "production_2", "staging_1", "staging_2"]):
        path = backup_root / name
        path.mkdir()
        os.utime(path, (100 + index, 100 + index))

    removed = prune_backups(backup_root, keep=1, environment="production")

    assert {p.name for p in removed} == {"production_1"}
    assert sorted(p.name for p in backup_root.iterdir()) == ["production_2", "staging_1", "staging_2"]


def test_prune_backups_removes_only_backups_older_than_days(tmp_path):
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    old = backup_root / "production_old"
    new = backup_root / "production_new"
    old.mkdir()
    new.mkdir()
    os.utime(old, (100, 100))
    os.utime(new, (200 + 86400 * 2, 200 + 86400 * 2))

    removed = prune_backups(backup_root, keep=99, newer_than_days=1, now=200 + 86400 * 2)

    assert [p.name for p in removed] == ["production_old"]
    assert [p.name for p in backup_root.iterdir()] == ["production_new"]


def test_s3_adapter_mirrors_backup_tree_locally(tmp_path):
    backup_dir = tmp_path / "backup_2026"
    backup_dir.mkdir()
    (backup_dir / "manifest.json").write_text("{}")
    adapter = S3Adapter(RemoteBackupConfig(bucket="bucket-name"), root=tmp_path / "remote")

    uploaded = adapter.upload_backup(backup_dir)

    assert uploaded == tmp_path / "remote" / "bucket-name" / "backup_2026"
    assert (uploaded / "manifest.json").read_text() == "{}"
