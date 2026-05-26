from __future__ import annotations
import tempfile
from pathlib import Path
from odooctl.adapters.filestore import FilestoreAdapter
from odooctl.adapters.postgres import PostgresAdapter
from odooctl.adapters.docker_compose import DockerComposeAdapter
from odooctl.adapters.reverse_proxy import public_url
from odooctl.config import load_config
from odooctl.odoo.sanitize import profile_sql
from odooctl.odoo.module_update import update_modules_compose
from odooctl.odoo.healthcheck import check_url


def execute(
    source: str,
    target: str,
    sanitize: bool | None = True,
    config_path: str = "odooctl.yml",
    sanitization_profile: str = "normal",
    preview: bool = False,
) -> str:
    cfg = load_config(config_path)
    src = cfg.env(source)
    dst = cfg.env(target)
    if not dst.clone_from:
        raise RuntimeError(f"Environment '{target}' is not configured as a clone target; set clone_from before cloning into it")
    if dst.clone_from != source:
        raise RuntimeError(f"Environment '{target}' must be cloned from '{dst.clone_from}', not '{source}'")
    should_sanitize = dst.sanitize if sanitize is None else sanitize
    if source == "production" and not should_sanitize:
        raise RuntimeError("Refusing to clone production data without sanitization enabled")
    compose_path = Path(config_path).parent / cfg.runtime.compose_file
    if not compose_path.exists():
        raise FileNotFoundError(f"Compose file not found: {compose_path}")

    base_url = public_url(dst.domain)
    if preview:
        print("[clone] preview")
        print(
            f"source={source} target={target} profile={sanitization_profile} "
            f"base_url={base_url} sanitize={'yes' if should_sanitize else 'no'}"
        )
        print(f"source_branch={src.branch} target_branch={dst.branch} clone_from={dst.clone_from}")
        print(f"affected_integrations={','.join(dst.update_modules) or 'none'}")
        print(f"production_source={'yes' if source == 'production' else 'no'}")
        return base_url
    pg = PostgresAdapter(cfg.postgres)
    fs = FilestoreAdapter()
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
        for sql in profile_sql(sanitization_profile, dst, cfg):
            pg.psql(dst.db_name, sql)
    compose = DockerComposeAdapter(cfg.runtime.compose_file)
    update_modules_compose(compose, cfg.odoo.service, dst.db_name, dst.update_modules)
    compose.restart(cfg.odoo.service)
    running_services = compose.ps()
    if cfg.odoo.service not in running_services:
        raise RuntimeError(f"Target service is not running after clone: {cfg.odoo.service}")
    url = base_url + cfg.healthcheck.path
    check_url(url, timeout=cfg.healthcheck.timeout_seconds, retries=cfg.healthcheck.retries, interval=cfg.healthcheck.interval_seconds)
    return base_url
