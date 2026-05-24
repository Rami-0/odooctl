from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import re
from odooctl.adapters.filestore import FilestoreAdapter
from odooctl.adapters.postgres import PostgresAdapter
from odooctl.adapters.s3 import S3Adapter
from odooctl.commands.restore import sha256_file
from odooctl.config import load_config
from odooctl.metadata.models import BackupManifest
from odooctl.metadata.store import MetadataStore
from odooctl.utils.paths import ensure_dir
from odooctl.utils.shell import run as shell_run

SENSITIVE_CONFIG_KEYS = re.compile(
    r"(password|passwd|admin_passwd|secret|token|api[_-]?key|smtp|oauth|webhook|license)",
    re.IGNORECASE,
)


def git_commit() -> str | None:
    r = shell_run(["git", "rev-parse", "--short", "HEAD"], check=False)
    return r.stdout.strip() or None


def prune_backups(backup_root: Path, keep: int) -> list[Path]:
    backups = sorted(
        [p for p in backup_root.iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    removed: list[Path] = []
    for path in backups[keep:]:
        removed.append(path)
        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_file() or child.is_symlink():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        path.rmdir()
    return removed


def redact_config_snapshot(text: str) -> str:
    redacted_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")) or "=" not in line:
            redacted_lines.append(line)
            continue
        key, value = line.split("=", 1)
        if SENSITIVE_CONFIG_KEYS.search(key):
            redacted_lines.append(f"{key.rstrip()} = ***REDACTED***")
        else:
            redacted_lines.append(f"{key.rstrip()} = {value.strip()}")
    return "\n".join(redacted_lines) + ("\n" if text.endswith("\n") else "")


def execute(environment: str, config_path: str = "odooctl.yml") -> str:
    cfg = load_config(config_path)
    env = cfg.env(environment)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    backup_id = f"{environment}_{ts}"
    backup_dir = ensure_dir(Path(cfg.backups.local_path) / backup_id)
    pg = PostgresAdapter(cfg.postgres)
    fs = FilestoreAdapter()
    pg.dump(env.db_name, backup_dir / "db.dump")
    fs.archive(env.filestore_path, backup_dir / "filestore.tar.zst")
    if Path(cfg.odoo.config_path).exists():
        text = Path(cfg.odoo.config_path).read_text()
        (backup_dir / "odoo.conf.redacted").write_text(redact_config_snapshot(text))
    commit = git_commit()
    (backup_dir / "git_commit.txt").write_text(commit or "unknown")
    (backup_dir / "docker_image.txt").write_text(cfg.odoo.image)
    manifest = BackupManifest(
        project=cfg.project.name,
        environment=environment,
        db_name=env.db_name,
        git_commit=commit,
        docker_image=cfg.odoo.image,
        odoo_version=cfg.project.odoo_version,
        checksums={
            "db_dump": sha256_file(backup_dir / "db.dump"),
            "filestore": sha256_file(backup_dir / "filestore.tar.zst"),
        },
    )
    (backup_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2))
    MetadataStore().save_backup_manifest(backup_id, manifest)
    if cfg.backups.remote:
        remote = S3Adapter(cfg.backups.remote)
        remote.upload_backup(backup_dir)
    keep_count = max(cfg.backups.retention.daily, cfg.backups.retention.weekly, cfg.backups.retention.monthly)
    prune_backups(Path(cfg.backups.local_path), keep=max(keep_count, 1))
    return backup_id
