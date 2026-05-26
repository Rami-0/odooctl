from __future__ import annotations

from pathlib import Path

from odooctl.adapters.docker_compose import DockerComposeAdapter
from odooctl.adapters.db import make_db_adapter as make_context_db_adapter
from odooctl.adapters.postgres import PostgresAdapter
from odooctl.adapters.reverse_proxy import public_url
from odooctl.commands.backup import execute as backup_execute, git_commit
from odooctl.context import ProjectContext
from odooctl.metadata.models import DeploymentMetadata
from odooctl.metadata.store import MetadataStore
from odooctl.odoo.healthcheck import check_url, with_db_selector
from odooctl.odoo.module_update import update_modules_compose
from odooctl.utils.shell import run


def _compose_adapter(compose_file: str, project_root: Path):
    try:
        return DockerComposeAdapter(compose_file, project_dir=str(project_root))
    except TypeError:
        return DockerComposeAdapter(compose_file)


def _store(root: Path):
    try:
        return MetadataStore(root)
    except TypeError:
        return MetadataStore()


def _git_commit(root: Path) -> str | None:
    try:
        return git_commit(root)
    except TypeError:
        return git_commit()


def _run(args: list[str], *, stream: bool = True, cwd: Path | None = None):
    try:
        return run(args, stream=stream, cwd=str(cwd) if cwd is not None else None)
    except TypeError:
        return run(args, stream=stream)


def _clean_worktree(root: Path) -> None:
    try:
        _assert_clean_worktree(cwd=root)
    except TypeError:
        _assert_clean_worktree()


def _assert_clean_worktree(operation: str = "deploy", *, cwd: str | Path | None = None) -> None:
    result = run(["git", "status", "--porcelain"], check=False, cwd=str(cwd) if cwd is not None else None)
    dirty_paths = result.stdout.strip()
    if dirty_paths:
        raise RuntimeError(f"Git worktree is dirty; commit or stash changes before {operation}:\n{dirty_paths}")


def _preflight(environment: str, branch: str | None, config_path: str):
    context = ProjectContext.from_config_path(config_path)
    cfg = context.config
    missing_env_vars = cfg.missing_env_vars()
    if missing_env_vars:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing_env_vars)}")
    env = cfg.env(environment)
    selected_branch = branch or env.branch
    if selected_branch != env.branch:
        raise RuntimeError(f"Branch '{selected_branch}' is not allowed for environment '{environment}'")
    compose_path = context.compose_file
    if not compose_path.exists():
        raise FileNotFoundError(f"Compose file not found: {compose_path}")
    filestore_path = context.resolve_path(env.filestore_path)
    if not filestore_path.exists():
        raise FileNotFoundError(f"Target filestore path not found: {filestore_path}")
    try:
        (make_context_db_adapter(context) if cfg.runtime.execution_mode == "docker" else PostgresAdapter(cfg.postgres)).ping(env.db_name)
    except Exception as exc:
        raise RuntimeError(
            f"Postgres connectivity check failed for database '{env.db_name}' "
            f"on {cfg.postgres.host}:{cfg.postgres.port}: {exc}"
        ) from exc
    _clean_worktree(context.root)
    return context, env, selected_branch


def execute(environment: str, branch: str | None = None, config_path: str = "odooctl.yml") -> None:
    print("[deploy] preflight")
    context, env, selected_branch = _preflight(environment, branch, config_path)
    cfg = context.config
    backup_id = None
    status = "failed"
    message = None
    scheme = cfg.healthcheck.scheme or env.scheme
    url = with_db_selector(public_url(env.domain, scheme=scheme, port=env.port) + cfg.healthcheck.path, env.db_name if env.db_selector else None)
    compose = _compose_adapter(cfg.runtime.compose_file, context.root)
    try:
        if environment == "production":
            print("[deploy] backup")
            backup_id = backup_execute(environment, config_path)
        print("[deploy] rollout")
        _run(["git", "fetch", "--all"], stream=True, cwd=context.root)
        _run(["git", "checkout", selected_branch], stream=True, cwd=context.root)
        _run(["git", "pull", "--ff-only"], stream=True, cwd=context.root)
        compose.pull(cfg.odoo.service)
        compose.up(cfg.odoo.service)
        try:
            update_modules_compose(
                compose,
                cfg.odoo.service,
                env.db_name,
                env.update_modules,
                db_host=cfg.odoo.db_host,
                db_user=cfg.odoo.db_user,
                db_password_env=cfg.odoo.db_password_env,
                config_path=cfg.odoo.config_path,
            )
        except TypeError:
            update_modules_compose(compose, cfg.odoo.service, env.db_name, env.update_modules)
        print("[deploy] verify")
        check_url(url, timeout=cfg.healthcheck.timeout_seconds, retries=cfg.healthcheck.retries, interval=cfg.healthcheck.interval_seconds)
        status = "success"
        print("[deploy] done")
    except Exception as exc:
        message = str(exc)
        if environment == "production":
            try:
                compose.restart(cfg.odoo.service)
            except Exception as recovery_exc:
                message = f"{message}; recovery restart failed: {recovery_exc}"
        raise
    finally:
        _store(context.state_dir).save_deployment(DeploymentMetadata(project=cfg.project.name, environment=environment, branch=selected_branch, commit=_git_commit(context.root), docker_image=cfg.odoo.image, backup=backup_id, modules_updated=env.update_modules, status=status, health_check_url=url, message=message))
