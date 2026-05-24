from __future__ import annotations
from pathlib import Path
from odooctl.adapters.filestore import FilestoreAdapter
from odooctl.adapters.postgres import PostgresAdapter
from odooctl.config import load_config
from odooctl.odoo.healthcheck import check_url
from odooctl.adapters.reverse_proxy import public_url

def execute(environment: str, backup: str = "latest", config_path: str = "odooctl.yml") -> None:
    cfg = load_config(config_path)
    env = cfg.env(environment)
    if backup == "latest":
        candidates = sorted(Path(cfg.backups.local_path).glob("production_*"))
        if not candidates:
            raise RuntimeError("No production backups found")
        backup_dir = candidates[-1]
    else:
        backup_dir = Path(cfg.backups.local_path) / backup
    PostgresAdapter(cfg.postgres).restore(env.db_name, backup_dir / "db.dump")
    FilestoreAdapter().restore_archive(backup_dir / "filestore.tar.zst", env.filestore_path)
    url = public_url(env.domain) + cfg.healthcheck.path
    check_url(url, timeout=cfg.healthcheck.timeout_seconds, retries=cfg.healthcheck.retries, interval=cfg.healthcheck.interval_seconds)
