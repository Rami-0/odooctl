"""Restore-point browser service — list and verify local backup integrity."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from odooctl.services.restore import sha256_file


@dataclass
class RestorePoint:
    backup_id: str
    environment: str
    timestamp: str
    integrity: str  # "ok" | "failed" | "unknown"


def list_restore_points(
    backups_root: str | Path,
    *,
    environment: str | None = None,
) -> list[RestorePoint]:
    """Return restore points sorted newest-first, optionally filtered by environment."""
    root = Path(backups_root)
    if not root.exists() or not root.is_dir():
        return []

    points: list[RestorePoint] = []
    for d in sorted(root.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        manifest_file = d / "manifest.json"
        if not manifest_file.exists():
            continue

        try:
            manifest = json.loads(manifest_file.read_text())
        except Exception:
            continue

        env = manifest.get("environment", "")
        if environment is not None and env != environment:
            continue

        # Parse timestamp from backup_id: {environment}_{timestamp}
        backup_id = manifest.get("backup_id", d.name)
        ts = backup_id[len(env) + 1:] if backup_id.startswith(env + "_") else ""

        integrity = _check_integrity(d, manifest)
        points.append(RestorePoint(
            backup_id=backup_id,
            environment=env,
            timestamp=ts,
            integrity=integrity,
        ))

    return points


def _check_integrity(backup_dir: Path, manifest: dict) -> str:
    checksums = manifest.get("checksums") or {}
    pairs = [("db_dump", "db.dump"), ("filestore", "filestore.tar")]
    for key, fname in pairs:
        expected = checksums.get(key)
        if not expected:
            return "unknown"
        fpath = backup_dir / fname
        if not fpath.exists():
            return "failed"
        try:
            actual = sha256_file(fpath)
        except Exception:
            return "failed"
        if actual != expected:
            return "failed"
    return "ok"
