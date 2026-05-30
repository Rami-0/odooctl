"""Restore service — validate and apply backup archives."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

from odooctl.adapters.db import make_db_adapter as make_context_db_adapter
from odooctl.adapters.filestore import FilestoreAdapter, make_filestore_adapter
from odooctl.adapters.postgres import PostgresAdapter
from odooctl.adapters.reverse_proxy import public_url
from odooctl.odoo.healthcheck import check_url, with_db_selector
from odooctl.services.models import RestoreResult

if TYPE_CHECKING:
    from odooctl.services.context import ServiceContext

REQUIRED_BACKUP_FILES = ("db.dump", "filestore.tar", "manifest.json")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_backup_dir(environment: str, backup: str, backups_root: Path) -> Path:
    if backup != "latest":
        return backups_root / backup
    candidates = sorted(backups_root.glob(f"{environment}_*"))
    if not candidates:
        raise RuntimeError(f"No backups found for environment: {environment}")
    return candidates[-1]


def validate_backup_dir(
    backup_dir: Path,
    *,
    expected_project: str | None = None,
    expected_environment: str | None = None,
    restore_mode: str = "full",
) -> dict:
    if not backup_dir.exists() or not backup_dir.is_dir():
        raise FileNotFoundError(f"Backup directory does not exist: {backup_dir}")
    missing = [name for name in REQUIRED_BACKUP_FILES if not (backup_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"Backup is missing required file(s): {', '.join(missing)}")
    manifest = json.loads((backup_dir / "manifest.json").read_text())
    if expected_project and manifest.get("project") != expected_project:
        raise RuntimeError(
            f"Backup project mismatch: expected {expected_project}, got {manifest.get('project')}"
        )
    if expected_environment and manifest.get("environment") != expected_environment:
        raise RuntimeError(
            f"Backup environment mismatch: expected {expected_environment}, got {manifest.get('environment')}"
        )
    if restore_mode == "full" and manifest.get("backup_mode", "full") != "full":
        raise RuntimeError(f"Unsupported backup mode for full restore: {manifest.get('backup_mode')}")
    checksums = manifest.get("checksums") or {}
    for key, file_name in (("db_dump", "db.dump"), ("filestore", "filestore.tar")):
        expected = checksums.get(key)
        if not expected:
            raise RuntimeError(f"Backup manifest is missing checksum for {file_name}")
        if sha256_file(backup_dir / file_name) != expected:
            raise RuntimeError(f"Backup checksum mismatch for {file_name}")
    return manifest


def run_restore(ctx: ServiceContext, environment: str, backup: str = "latest") -> RestoreResult:
    cfg = ctx.project.config
    env = cfg.env(environment)
    backup_dir = resolve_backup_dir(environment, backup, ctx.project.backups_dir)
    validate_backup_dir(backup_dir, expected_project=cfg.project.name, expected_environment=environment, restore_mode="full")
    pg = make_context_db_adapter(ctx.project) if cfg.runtime.execution_mode == "docker" else PostgresAdapter(cfg.postgres)
    pg.restore(env.db_name, backup_dir / "db.dump")
    target_filestore = env.filestore_path if env.filestore_volume else str(ctx.project.resolve_path(env.filestore_path))
    fs = make_filestore_adapter(ctx.project, env) if env.filestore_volume else FilestoreAdapter()
    fs.restore_archive(backup_dir / "filestore.tar", target_filestore)
    scheme = cfg.healthcheck.scheme or env.scheme
    url = with_db_selector(
        public_url(env.domain, scheme=scheme, port=env.port) + cfg.healthcheck.path,
        env.db_name if env.db_selector else None,
    )
    check_url(url, timeout=cfg.healthcheck.timeout_seconds, retries=cfg.healthcheck.retries, interval=cfg.healthcheck.interval_seconds)
    return RestoreResult(backup_id=backup_dir.name)
