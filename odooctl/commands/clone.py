from __future__ import annotations
import tempfile
from pathlib import Path
from odooctl.adapters.filestore import FilestoreAdapter, make_filestore_adapter
from odooctl.adapters.db import make_db_adapter as make_context_db_adapter
from odooctl.adapters.postgres import PostgresAdapter
from odooctl.adapters.docker_compose import DockerComposeAdapter
from odooctl.adapters.reverse_proxy import public_url
from odooctl.context import ProjectContext
from odooctl.odoo.db_swap import swap_temp_database
from odooctl.odoo.sanitize import sanitize_database
from odooctl.odoo.module_update import update_modules_compose
from odooctl.odoo.healthcheck import check_url, with_db_selector


def _compose_adapter(compose_file: str, project_root: Path):
    try:
        return DockerComposeAdapter(compose_file, project_dir=str(project_root))
    except TypeError:
        # Preserve compatibility with tests and third-party monkeypatches that
        # replace the adapter with a one-argument dummy.
        return DockerComposeAdapter(compose_file)


def execute(
    source: str,
    target: str,
    sanitize: bool | None = True,
    config_path: str = "odooctl.yml",
    sanitization_profile: str = "normal",
    preview: bool = False,
) -> str:
    context = ProjectContext.from_config_path(config_path)
    cfg = context.config
    src = cfg.env(source)
    dst = cfg.env(target)
    if not dst.clone_from:
        raise RuntimeError(f"Environment '{target}' is not configured as a clone target; set clone_from before cloning into it")
    if dst.clone_from != source:
        raise RuntimeError(f"Environment '{target}' must be cloned from '{dst.clone_from}', not '{source}'")
    should_sanitize = dst.sanitize if sanitize is None else sanitize
    if source == "production" and not should_sanitize:
        raise RuntimeError("Refusing to clone production data without sanitization enabled")
    compose_path = context.compose_file
    if not compose_path.exists():
        raise FileNotFoundError(f"Compose file not found: {compose_path}")

    scheme = cfg.healthcheck.scheme or dst.scheme
    base_url = public_url(dst.domain, scheme=scheme, port=dst.port)
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

    missing_env_vars = cfg.missing_env_vars()
    if missing_env_vars:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing_env_vars)}")

    pg = make_context_db_adapter(context) if cfg.runtime.execution_mode == "docker" else PostgresAdapter(cfg.postgres)
    fs = make_filestore_adapter(context, dst) if dst.filestore_volume else FilestoreAdapter()
    temp_db = f"{dst.db_name}{cfg.sanitization.temp_db_suffix}"
    if temp_db == dst.db_name:
        raise RuntimeError("Configured sanitization.temp_db_suffix must produce a temporary database distinct from the target")
    if hasattr(pg, "clone_db_in_container"):
        pg.clone_db_in_container(src.db_name, temp_db)  # type: ignore[attr-defined]
    else:
        with tempfile.NamedTemporaryFile(prefix="odooctl-clone-", suffix=".dump", delete=False) as tmp:
            tmp_dump = Path(tmp.name)
        try:
            pg.dump(src.db_name, tmp_dump)
            pg.restore(temp_db, tmp_dump)
        finally:
            tmp_dump.unlink(missing_ok=True)
    src_filestore = src.filestore_path if src.filestore_volume else str(context.resolve_path(src.filestore_path))
    dst_filestore = dst.filestore_path if dst.filestore_volume else str(context.resolve_path(dst.filestore_path))
    fs.copy(src_filestore, dst_filestore)
    if should_sanitize:
        sanitize_database(pg, temp_db, dst, cfg, sanitization_profile, sql_files=context.sanitization_sql_files())
    swap_temp_database(pg, temp_db=temp_db, target_db=dst.db_name, target_env_name=target)
    compose = _compose_adapter(cfg.runtime.compose_file, context.root)
    try:
        update_modules_compose(
            compose,
            cfg.odoo.service,
            dst.db_name,
            dst.update_modules,
            db_host=cfg.odoo.db_host,
            db_user=cfg.odoo.db_user,
            db_password_env=cfg.odoo.db_password_env,
            config_path=cfg.odoo.config_path,
        )
    except TypeError:
        update_modules_compose(compose, cfg.odoo.service, dst.db_name, dst.update_modules)
    compose.restart(cfg.odoo.service)
    running_services = compose.ps()
    if cfg.odoo.service not in running_services:
        raise RuntimeError(f"Target service is not running after clone: {cfg.odoo.service}")
    url = with_db_selector(base_url + cfg.healthcheck.path, dst.db_name if dst.db_selector else None)
    check_url(url, timeout=cfg.healthcheck.timeout_seconds, retries=cfg.healthcheck.retries, interval=cfg.healthcheck.interval_seconds)
    return base_url
