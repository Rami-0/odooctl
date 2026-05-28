from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import re
from odooctl.adapters.filestore import FilestoreAdapter, make_filestore_adapter
from odooctl.adapters.db import make_db_adapter as make_context_db_adapter
from odooctl.adapters.postgres import PostgresAdapter
from odooctl.adapters.s3 import S3Adapter
from odooctl.commands.restore import sha256_file
from odooctl.context import ProjectContext
from odooctl.metadata.models import BackupManifest
from odooctl.metadata.store import MetadataStore
from odooctl.utils.paths import ensure_dir
from odooctl.utils.shell import run as shell_run

SENSITIVE_CONFIG_KEYS = re.compile(
    r"(password|passwd|admin_passwd|secret|token|api[_-]?key|smtp|oauth|webhook|license)",
    re.IGNORECASE,
)


def git_commit(cwd: str | Path | None = None) -> str | None:
    r = shell_run(["git", "rev-parse", "--short", "HEAD"], check=False, cwd=str(cwd) if cwd is not None else None)
    return r.stdout.strip() or None


def _remove_tree(path: Path) -> None:
    for child in sorted(path.rglob("*"), reverse=True):
        if child.is_file() or child.is_symlink():
            child.unlink()
        elif child.is_dir():
            child.rmdir()
    path.rmdir()


def prune_backups(
    backup_root: Path,
    keep: int,
    *,
    environment: str | None = None,
    newer_than_days: int | None = None,
    now: float | None = None,
) -> list[Path]:
    if not backup_root.exists():
        return []
    backups = sorted(
        [p for p in backup_root.iterdir() if p.is_dir() and (environment is None or p.name.startswith(f"{environment}_"))],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    removed: list[Path] = []
    keep_count = max(keep, 0)
    to_remove = list(backups[keep_count:])
    if newer_than_days is not None:
        cutoff = (now if now is not None else datetime.now(timezone.utc).timestamp()) - (newer_than_days * 86400)
        to_remove.extend([p for p in backups[:keep_count] if p.stat().st_mtime < cutoff])
    for path in sorted(set(to_remove), key=lambda p: p.stat().st_mtime):
        removed.append(path)
        _remove_tree(path)
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
    context = ProjectContext.from_config_path(config_path)
    cfg = context.config
    env = cfg.env(environment)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    backup_id = f"{environment}_{ts}"
    backup_dir = ensure_dir(context.backups_dir / backup_id)
    pg = make_context_db_adapter(context) if cfg.runtime.execution_mode == "docker" else PostgresAdapter(cfg.postgres)
    fs = make_filestore_adapter(context, env) if env.filestore_volume else FilestoreAdapter()
    pg.dump(env.db_name, backup_dir / "db.dump")
    filestore_path = env.filestore_path if env.filestore_volume else str(context.resolve_path(env.filestore_path))
    fs.archive(filestore_path, backup_dir / "filestore.tar")
    if context.odoo_config_path.exists():
        text = context.odoo_config_path.read_text()
        (backup_dir / "odoo.conf.redacted").write_text(redact_config_snapshot(text))
    commit = git_commit(context.root)
    (backup_dir / "git_commit.txt").write_text(commit or "unknown")
    (backup_dir / "docker_image.txt").write_text(cfg.odoo.image)
    manifest = BackupManifest(
        backup_id=backup_id,
        project=cfg.project.name,
        environment=environment,
        db_name=env.db_name,
        filestore_path=env.filestore_path,
        artifact_paths=["db.dump", "filestore.tar"],
        backup_mode="full",
        git_commit=commit,
        docker_image=cfg.odoo.image,
        odoo_version=cfg.project.odoo_version,
        checksums={
            "db_dump": sha256_file(backup_dir / "db.dump"),
            "filestore": sha256_file(backup_dir / "filestore.tar"),
        },
    )
    (backup_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2))
    MetadataStore(context.state_dir).save_backup_manifest(backup_id, manifest)
    if cfg.backups.remote:
        remote = S3Adapter(cfg.backups.remote, root=context.state_dir / "remote-backups")
        remote.upload_backup(backup_dir)
    keep_count = max(cfg.backups.retention.daily, cfg.backups.retention.weekly, cfg.backups.retention.monthly)
    prune_backups(context.backups_dir, keep=max(keep_count, 1), environment=environment)
    return backup_id
