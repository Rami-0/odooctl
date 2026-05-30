"""TDD tests for M9 promote service."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from odooctl.services import promote as promote_svc
from odooctl.services.context import ServiceContext
from odooctl.services.models import BackupResult, PromoteResult


CONFIG = """\
project:
  name: demo
  odoo_version: "19.0"
runtime:
  compose_file: docker-compose.yml
healthcheck:
  path: /web/health
  timeout_seconds: 10
  retries: 3
  interval_seconds: 1
odoo:
  image: registry/odoo:latest
  service: odoo
environments:
  production:
    tier: production
    protected: true
    branch: main
    domain: odoo.example.com
    db_name: odoo_prod
    filestore_path: /srv/filestore/prod
    update_modules: [sale, stock]
  staging:
    tier: staging
    branch: staging
    domain: staging.example.com
    db_name: odoo_staging
    filestore_path: /srv/filestore/staging
    clone_from: production
    sanitize: true
    promotes_to: production
    update_modules: [sale]
"""

CONFIG_NO_PROMOTES_TO = """\
project:
  name: demo
  odoo_version: "19.0"
runtime:
  compose_file: docker-compose.yml
healthcheck:
  path: /web/health
  timeout_seconds: 10
  retries: 3
  interval_seconds: 1
odoo:
  image: registry/odoo:latest
  service: odoo
environments:
  production:
    branch: main
    domain: odoo.example.com
    db_name: odoo_prod
    filestore_path: /srv/filestore/prod
  staging:
    branch: staging
    domain: staging.example.com
    db_name: odoo_staging
    filestore_path: /srv/filestore/staging
    clone_from: production
    sanitize: true
"""


class DummyCompose:
    def __init__(self, compose_file: str, **kwargs):
        self.calls: list[tuple] = []

    def pull(self, service: str | None = None):
        self.calls.append(("pull", service))

    def up(self, service: str | None = None):
        self.calls.append(("up", service))

    def restart(self, service: str):
        self.calls.append(("restart", service))


class DummyMetaStore:
    def __init__(self):
        self.saved: list = []

    def save_deployment(self, metadata):
        self.saved.append(metadata)
        return Path("/tmp/deploy.json")


def _make_ctx(tmp_path: Path, config_text: str) -> ServiceContext:
    cfg_path = tmp_path / "odooctl.yml"
    cfg_path.write_text(config_text)
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    return ServiceContext.from_config_path(str(cfg_path), root=tmp_path)


# ─── promote_preview ─────────────────────────────────────────────────────────

def test_promote_preview_returns_result_with_no_side_effects(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, CONFIG)
    side_effects = []

    monkeypatch.setattr(promote_svc, "backup_execute", lambda *a, **k: side_effects.append("backup"))
    monkeypatch.setattr(promote_svc, "run", lambda *a, **k: side_effects.append("run"))
    monkeypatch.setattr(promote_svc, "check_url", lambda *a, **k: side_effects.append("healthcheck"))
    monkeypatch.setattr(promote_svc, "DockerComposeAdapter", lambda *a, **k: side_effects.append("compose"))

    result = promote_svc.promote_preview(ctx, "staging", "production")

    assert result.status == "preview"
    assert result.source == "staging"
    assert result.target == "production"
    assert side_effects == []  # no real side effects


def test_promote_preview_raises_when_promotes_to_not_configured(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, CONFIG_NO_PROMOTES_TO)
    monkeypatch.setattr(promote_svc, "check_url", lambda *a, **k: None)

    with pytest.raises(RuntimeError, match="does not promote to"):
        promote_svc.promote_preview(ctx, "staging", "production")


def test_promote_preview_raises_when_wrong_target(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, CONFIG)
    monkeypatch.setattr(promote_svc, "check_url", lambda *a, **k: None)

    with pytest.raises(RuntimeError, match="does not promote to"):
        promote_svc.promote_preview(ctx, "staging", "staging")


def test_promote_preview_allowed_for_protected_target_without_confirm(tmp_path: Path):
    ctx = _make_ctx(tmp_path, CONFIG)  # production is protected=true

    result = promote_svc.promote_preview(ctx, "staging", "production")
    assert result.status == "preview"


# ─── run_promote — validation / preflight ────────────────────────────────────

def test_run_promote_validates_promotes_to_config(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, CONFIG_NO_PROMOTES_TO)
    monkeypatch.setattr(promote_svc, "check_url", lambda *a, **k: None)

    with pytest.raises(RuntimeError, match="does not promote to"):
        promote_svc.run_promote(ctx, "staging", "production")


def test_run_promote_raises_when_compose_file_missing(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, CONFIG)
    (tmp_path / "docker-compose.yml").unlink()
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")
    monkeypatch.setattr(promote_svc, "check_url", lambda *a, **k: None)

    with pytest.raises(FileNotFoundError, match="Compose file not found"):
        promote_svc.run_promote(ctx, "staging", "production")


def test_run_promote_raises_when_missing_env_vars(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, CONFIG)
    monkeypatch.delenv("ODOO_DB_PASSWORD", raising=False)
    monkeypatch.setattr(promote_svc, "check_url", lambda *a, **k: None)

    with pytest.raises(RuntimeError, match="Missing required environment variables"):
        promote_svc.run_promote(ctx, "staging", "production")


# ─── run_promote — protected target ──────────────────────────────────────────

def test_run_promote_requires_confirm_for_protected_target(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, CONFIG)  # production is protected=true
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")

    with pytest.raises(RuntimeError, match="protected"):
        promote_svc.run_promote(ctx, "staging", "production")  # no confirm


def test_run_promote_confirm_true_allows_protected_target(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, CONFIG)
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")
    store = DummyMetaStore()

    monkeypatch.setattr(promote_svc, "check_url", lambda *a, **k: None)
    monkeypatch.setattr(promote_svc, "backup_execute", lambda ctx, env: BackupResult(backup_id="bk"))
    monkeypatch.setattr(promote_svc, "run", lambda *a, **k: None)
    monkeypatch.setattr(promote_svc, "DockerComposeAdapter", lambda *a, **k: DummyCompose("dc.yml"))
    monkeypatch.setattr(promote_svc, "update_modules_compose", lambda *a, **k: None)
    monkeypatch.setattr(promote_svc, "git_commit", lambda cwd=None: "abc")
    monkeypatch.setattr(promote_svc, "MetadataStore", lambda root: store)

    result = promote_svc.run_promote(ctx, "staging", "production", confirm=True)
    assert result.status == "success"


# ─── run_promote — dirty worktree preflight ──────────────────────────────────

def test_run_promote_dirty_worktree_blocks_before_backup(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, CONFIG)
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")
    backup_calls: list = []

    def fake_run(args, **kwargs):
        if args[1] == "status":
            return SimpleNamespace(stdout=" M dirty_file.py")
        return None

    monkeypatch.setattr(promote_svc, "check_url", lambda *a, **k: None)
    monkeypatch.setattr(promote_svc, "run", fake_run)
    monkeypatch.setattr(
        promote_svc, "backup_execute",
        lambda ctx, env: (backup_calls.append(env) or BackupResult(backup_id="x")),
    )

    with pytest.raises(RuntimeError, match="dirty"):
        promote_svc.run_promote(ctx, "staging", "production", confirm=True)

    assert backup_calls == []  # backup must not run if worktree is dirty


# ─── run_promote — ordering ───────────────────────────────────────────────────

def test_run_promote_checks_source_health_before_backup(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, CONFIG)
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")
    order: list[str] = []

    monkeypatch.setattr(promote_svc, "check_url", lambda url, **k: order.append(f"healthcheck:{url}"))
    monkeypatch.setattr(
        promote_svc, "backup_execute",
        lambda ctx, env: (order.append("backup") or BackupResult(backup_id="prod_2026")),
    )
    monkeypatch.setattr(promote_svc, "run", lambda args, **kwargs: order.append(f"run:{args[1]}"))
    monkeypatch.setattr(promote_svc, "DockerComposeAdapter", lambda *a, **k: DummyCompose("dc.yml"))
    monkeypatch.setattr(promote_svc, "update_modules_compose", lambda *a, **k: order.append("modules"))
    monkeypatch.setattr(promote_svc, "git_commit", lambda cwd=None: "abc123")
    monkeypatch.setattr(promote_svc, "MetadataStore", lambda root: DummyMetaStore())

    promote_svc.run_promote(ctx, "staging", "production", confirm=True)

    source_hc_idx = order.index("healthcheck:https://staging.example.com/web/health")
    backup_idx = order.index("backup")
    assert backup_idx > source_hc_idx


def test_run_promote_preflight_and_backup_before_git_operations(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, CONFIG)
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")
    order: list[str] = []

    monkeypatch.setattr(promote_svc, "check_url", lambda *a, **k: None)
    monkeypatch.setattr(
        promote_svc, "backup_execute",
        lambda ctx, env: (order.append("backup") or BackupResult(backup_id="prod_2026")),
    )
    monkeypatch.setattr(promote_svc, "run", lambda args, **kwargs: order.append(f"git:{args[1]}"))
    monkeypatch.setattr(promote_svc, "DockerComposeAdapter", lambda *a, **k: DummyCompose("dc.yml"))
    monkeypatch.setattr(promote_svc, "update_modules_compose", lambda *a, **k: None)
    monkeypatch.setattr(promote_svc, "git_commit", lambda cwd=None: "abc123")
    monkeypatch.setattr(promote_svc, "MetadataStore", lambda root: DummyMetaStore())

    result = promote_svc.run_promote(ctx, "staging", "production", confirm=True)

    assert result.backup_id == "prod_2026"
    # preflight (status) before backup, backup before any mutating git operation
    assert order.index("git:status") < order.index("backup") < order.index("git:fetch")


# ─── run_promote — source→target merge ───────────────────────────────────────

def test_run_promote_merges_source_into_target_via_ff_only(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, CONFIG)
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")
    git_calls: list = []

    monkeypatch.setattr(promote_svc, "check_url", lambda *a, **k: None)
    monkeypatch.setattr(promote_svc, "backup_execute", lambda ctx, env: BackupResult(backup_id="prod_2026"))
    monkeypatch.setattr(promote_svc, "run", lambda args, **kwargs: git_calls.append(list(args)))
    monkeypatch.setattr(promote_svc, "DockerComposeAdapter", lambda *a, **k: DummyCompose("dc.yml"))
    monkeypatch.setattr(promote_svc, "update_modules_compose", lambda *a, **k: None)
    monkeypatch.setattr(promote_svc, "git_commit", lambda cwd=None: "abc")
    monkeypatch.setattr(promote_svc, "MetadataStore", lambda root: DummyMetaStore())

    promote_svc.run_promote(ctx, "staging", "production", confirm=True)

    # checkout target branch first, then ff-merge source
    checkout_calls = [c for c in git_calls if "checkout" in c]
    assert checkout_calls[0] == ["git", "checkout", "main"]
    merge_calls = [c for c in git_calls if "merge" in c]
    assert ["git", "merge", "--ff-only", "staging"] in merge_calls
    # no plain pull --ff-only
    assert not any(c == ["git", "pull", "--ff-only"] for c in git_calls)


# ─── run_promote — success metadata ──────────────────────────────────────────

def test_run_promote_success_records_metadata(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, CONFIG)
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")
    store = DummyMetaStore()

    monkeypatch.setattr(promote_svc, "check_url", lambda *a, **k: None)
    monkeypatch.setattr(promote_svc, "backup_execute", lambda ctx, env: BackupResult(backup_id="prod_2026"))
    monkeypatch.setattr(promote_svc, "run", lambda *a, **k: None)
    monkeypatch.setattr(promote_svc, "DockerComposeAdapter", lambda *a, **k: DummyCompose("dc.yml"))
    monkeypatch.setattr(promote_svc, "update_modules_compose", lambda *a, **k: None)
    monkeypatch.setattr(promote_svc, "git_commit", lambda cwd=None: "feedbeef")
    monkeypatch.setattr(promote_svc, "MetadataStore", lambda root: store)

    result = promote_svc.run_promote(ctx, "staging", "production", confirm=True)

    assert result.status == "success"
    assert result.backup_id == "prod_2026"
    assert len(store.saved) == 1
    assert store.saved[0].status == "success"
    assert store.saved[0].commit == "feedbeef"
    assert store.saved[0].backup == "prod_2026"
    assert store.saved[0].environment == "production"


# ─── run_promote — rollback on failure ───────────────────────────────────────

def test_run_promote_rolls_back_on_healthcheck_failure(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, CONFIG)
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")
    rollback_calls: list[str] = []
    store = DummyMetaStore()

    def fake_check_url(url, **kwargs):
        if "staging" in url:
            return
        raise RuntimeError("target healthcheck failed")

    monkeypatch.setattr(promote_svc, "check_url", fake_check_url)
    monkeypatch.setattr(promote_svc, "backup_execute", lambda ctx, env: BackupResult(backup_id="prod_2026"))
    monkeypatch.setattr(promote_svc, "run", lambda *a, **k: None)
    monkeypatch.setattr(promote_svc, "DockerComposeAdapter", lambda *a, **k: DummyCompose("dc.yml"))
    monkeypatch.setattr(promote_svc, "update_modules_compose", lambda *a, **k: None)
    monkeypatch.setattr(promote_svc, "git_commit", lambda cwd=None: "abc123")
    monkeypatch.setattr(promote_svc, "MetadataStore", lambda root: store)
    monkeypatch.setattr(promote_svc, "run_restore", lambda ctx, env, backup_id: rollback_calls.append(backup_id))

    with pytest.raises(RuntimeError, match="Promote failed"):
        promote_svc.run_promote(ctx, "staging", "production", confirm=True)

    assert rollback_calls == ["prod_2026"]
    assert store.saved[0].status == "failed"


def test_run_promote_code_rollback_resets_to_pre_promote_commit(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, CONFIG)
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")
    git_calls: list = []

    def fake_check_url(url, **kwargs):
        if "staging" in url:
            return
        raise RuntimeError("target healthcheck failed")

    monkeypatch.setattr(promote_svc, "check_url", fake_check_url)
    monkeypatch.setattr(promote_svc, "backup_execute", lambda ctx, env: BackupResult(backup_id="prod_bk"))
    monkeypatch.setattr(promote_svc, "run", lambda args, **kwargs: git_calls.append(list(args)))
    monkeypatch.setattr(promote_svc, "DockerComposeAdapter", lambda *a, **k: DummyCompose("dc.yml"))
    monkeypatch.setattr(promote_svc, "update_modules_compose", lambda *a, **k: None)
    monkeypatch.setattr(promote_svc, "git_commit", lambda cwd=None: "pre_abc")
    monkeypatch.setattr(promote_svc, "MetadataStore", lambda root: DummyMetaStore())
    monkeypatch.setattr(promote_svc, "run_restore", lambda *a, **k: None)

    with pytest.raises(RuntimeError, match="rolled back"):
        promote_svc.run_promote(ctx, "staging", "production", confirm=True)

    reset_calls = [c for c in git_calls if "reset" in c]
    assert ["git", "reset", "--hard", "pre_abc"] in reset_calls


def test_run_promote_code_rollback_redeploys_service(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, CONFIG)
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")
    compose = DummyCompose("dc.yml")

    def fake_check_url(url, **kwargs):
        if "staging" in url:
            return
        raise RuntimeError("target healthcheck failed")

    monkeypatch.setattr(promote_svc, "check_url", fake_check_url)
    monkeypatch.setattr(promote_svc, "backup_execute", lambda ctx, env: BackupResult(backup_id="prod_bk"))
    monkeypatch.setattr(promote_svc, "run", lambda *a, **k: None)
    monkeypatch.setattr(promote_svc, "DockerComposeAdapter", lambda *a, **k: compose)
    monkeypatch.setattr(promote_svc, "update_modules_compose", lambda *a, **k: None)
    monkeypatch.setattr(promote_svc, "git_commit", lambda cwd=None: "pre_abc")
    monkeypatch.setattr(promote_svc, "MetadataStore", lambda root: DummyMetaStore())
    monkeypatch.setattr(promote_svc, "run_restore", lambda *a, **k: None)

    with pytest.raises(RuntimeError):
        promote_svc.run_promote(ctx, "staging", "production", confirm=True)

    # compose.up called once during deploy attempt, once during code rollback redeploy
    up_calls = [c for c in compose.calls if c[0] == "up"]
    assert len(up_calls) == 2, f"Expected 2 up calls (deploy + rollback redeploy), got {up_calls}"


def test_run_promote_rollback_incomplete_honest_error_on_data_restore_failure(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, CONFIG)
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")
    store = DummyMetaStore()

    def fake_check_url(url, **kwargs):
        if "staging" in url:
            return
        raise RuntimeError("target health failed")

    monkeypatch.setattr(promote_svc, "check_url", fake_check_url)
    monkeypatch.setattr(promote_svc, "backup_execute", lambda ctx, env: BackupResult(backup_id="prod_bk"))
    monkeypatch.setattr(promote_svc, "run", lambda *a, **k: None)
    monkeypatch.setattr(promote_svc, "DockerComposeAdapter", lambda *a, **k: DummyCompose("dc.yml"))
    monkeypatch.setattr(promote_svc, "update_modules_compose", lambda *a, **k: None)
    monkeypatch.setattr(promote_svc, "git_commit", lambda cwd=None: "abc")
    monkeypatch.setattr(promote_svc, "MetadataStore", lambda root: store)
    monkeypatch.setattr(promote_svc, "run_restore", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("restore failed")))

    with pytest.raises(RuntimeError) as exc_info:
        promote_svc.run_promote(ctx, "staging", "production", confirm=True)
    assert "incomplete" in str(exc_info.value).lower()
    assert "manual intervention" in str(exc_info.value).lower()


def test_run_promote_rollback_incomplete_honest_error_on_code_reset_failure(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, CONFIG)
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")

    def fake_check_url(url, **kwargs):
        if "staging" in url:
            return
        raise RuntimeError("target health failed")

    def fake_run(args, **kwargs):
        if args[1:3] == ["reset", "--hard"]:
            raise RuntimeError("git reset failed")

    monkeypatch.setattr(promote_svc, "check_url", fake_check_url)
    monkeypatch.setattr(promote_svc, "backup_execute", lambda ctx, env: BackupResult(backup_id="prod_bk"))
    monkeypatch.setattr(promote_svc, "run", fake_run)
    monkeypatch.setattr(promote_svc, "DockerComposeAdapter", lambda *a, **k: DummyCompose("dc.yml"))
    monkeypatch.setattr(promote_svc, "update_modules_compose", lambda *a, **k: None)
    monkeypatch.setattr(promote_svc, "git_commit", lambda cwd=None: "abc")
    monkeypatch.setattr(promote_svc, "MetadataStore", lambda root: DummyMetaStore())
    monkeypatch.setattr(promote_svc, "run_restore", lambda *a, **k: None)

    with pytest.raises(RuntimeError, match="incomplete"):
        promote_svc.run_promote(ctx, "staging", "production", confirm=True)


def test_run_promote_records_failure_metadata_even_on_rollback(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, CONFIG)
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")
    store = DummyMetaStore()

    def fake_check_url(url, **kwargs):
        if "staging" in url:
            return
        raise RuntimeError("production health failed")

    monkeypatch.setattr(promote_svc, "check_url", fake_check_url)
    monkeypatch.setattr(promote_svc, "backup_execute", lambda ctx, env: BackupResult(backup_id="prod_bk"))
    monkeypatch.setattr(promote_svc, "run", lambda *a, **k: None)
    monkeypatch.setattr(promote_svc, "DockerComposeAdapter", lambda *a, **k: DummyCompose("dc.yml"))
    monkeypatch.setattr(promote_svc, "update_modules_compose", lambda *a, **k: None)
    monkeypatch.setattr(promote_svc, "git_commit", lambda cwd=None: "abc")
    monkeypatch.setattr(promote_svc, "MetadataStore", lambda root: store)
    monkeypatch.setattr(promote_svc, "run_restore", lambda *a, **k: None)

    with pytest.raises(RuntimeError):
        promote_svc.run_promote(ctx, "staging", "production", confirm=True)

    assert len(store.saved) == 1
    assert store.saved[0].status == "failed"
    assert store.saved[0].backup == "prod_bk"


# ─── run_promote — source health abort ───────────────────────────────────────

def test_run_promote_source_health_failure_aborts_before_backup(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, CONFIG)
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")
    backup_calls: list = []

    monkeypatch.setattr(
        promote_svc, "check_url",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("staging down")),
    )
    monkeypatch.setattr(
        promote_svc, "backup_execute",
        lambda ctx, env: (backup_calls.append(env) or BackupResult(backup_id="x")),
    )

    with pytest.raises(RuntimeError, match="staging down"):
        promote_svc.run_promote(ctx, "staging", "production", confirm=True)

    assert backup_calls == []  # no backup if source is unhealthy


# ─── CLI — promote --yes ──────────────────────────────────────────────────────

def test_cli_promote_requires_yes_for_protected_target(tmp_path: Path, monkeypatch):
    from typer.testing import CliRunner
    from odooctl.main import app

    config = tmp_path / "odooctl.yml"
    config.write_text(CONFIG)
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")

    runner = CliRunner()
    result = runner.invoke(app, ["--project-dir", str(tmp_path), "promote", "staging", "production"])
    assert result.exit_code != 0
    combined = result.output + str(result.exception or "")
    assert "protected" in combined.lower()


def test_cli_promote_yes_flag_bypasses_protection(tmp_path: Path, monkeypatch):
    from typer.testing import CliRunner
    from odooctl.main import app

    config = tmp_path / "odooctl.yml"
    config.write_text(CONFIG)
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")

    # Mock the service to avoid real git/docker
    import odooctl.services.promote as svc

    monkeypatch.setattr(svc, "check_url", lambda *a, **k: None)
    monkeypatch.setattr(svc, "backup_execute", lambda *a, **k: BackupResult(backup_id="bk1"))
    monkeypatch.setattr(svc, "run", lambda *a, **k: None)
    monkeypatch.setattr(svc, "DockerComposeAdapter", lambda *a, **k: DummyCompose("dc.yml"))
    monkeypatch.setattr(svc, "update_modules_compose", lambda *a, **k: None)
    monkeypatch.setattr(svc, "git_commit", lambda cwd=None: "abc")
    monkeypatch.setattr(svc, "MetadataStore", lambda root: DummyMetaStore())

    runner = CliRunner()
    result = runner.invoke(
        app, ["--project-dir", str(tmp_path), "promote", "staging", "production", "--yes"]
    )
    assert result.exit_code == 0, result.output
    assert "bk1" in result.output


# ─── PromoteResult model ─────────────────────────────────────────────────────

def test_promote_result_defaults():
    r = PromoteResult(source="staging", target="production", status="success")
    assert r.backup_id is None
    assert r.rolled_back is False
    assert r.message is None
