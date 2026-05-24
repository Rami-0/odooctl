from __future__ import annotations
import tempfile
from pathlib import Path
from odooctl.adapters.filestore import FilestoreAdapter
from odooctl.adapters.postgres import PostgresAdapter
from odooctl.adapters.docker_compose import DockerComposeAdapter
from odooctl.adapters.reverse_proxy import public_url
from odooctl.config import load_config
from odooctl.odoo.sanitize import sanitize_database
from odooctl.odoo.module_update import update_modules_compose
from odooctl.odoo.healthcheck import check_url


def execute(source: str, target: str, sanitize: bool | None = True, config_path: str = "odooctl.yml") -> str:
    cfg = load_config(config_path)
    src = cfg.env(source)
    dst = cfg.env(target)
    pg = PostgresAdapter(cfg.postgres)
    fs = FilestoreAdapter()
    should_sanitize = dst.sanitize if sanitize is None else sanitize
    # Direct dump/restore keeps db + filestore in one explicit clone flow.
    with tempfile.NamedTemporaryFile(prefix="odooctl-clone-", suffix=".dump", delete=False) as tmp:
        tmp_dump = Path(tmp.name)
    try:
        pg.dump(src.db_name, tmp_dump)
        pg.restore(dst.db_name, tmp_dump)
    finally:
        tmp_dump.unlink(missing_ok=True)
    fs.copy(src.filestore_path, dst.filestore_path)
    if should_sanitize:
        sanitize_database(pg, dst.db_name, dst, cfg)
    compose = DockerComposeAdapter(cfg.runtime.compose_file)
    update_modules_compose(compose, cfg.odoo.service, dst.db_name, dst.update_modules)
    compose.restart(cfg.odoo.service)
    url = public_url(dst.domain) + cfg.healthcheck.path
    check_url(url, timeout=cfg.healthcheck.timeout_seconds, retries=cfg.healthcheck.retries, interval=cfg.healthcheck.interval_seconds)
    return public_url(dst.domain)
