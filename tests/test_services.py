"""TDD tests for M6 service layer — written before service modules exist."""
from __future__ import annotations

from pathlib import Path

import pytest

from odooctl.services.models import (
    BackupResult,
    CloneResult,
    DeployResult,
    DoctorReport,
    EnvironmentSummary,
    RestoreResult,
    ServiceResult,
    StatusReport,
)
from odooctl.services.context import ServiceContext
from odooctl.services import backup as backup_svc
from odooctl.services import clone as clone_svc
from odooctl.services import project as project_svc
from odooctl.services import restore as restore_svc


MINIMAL_CONFIG = """\
project:
  name: demo
  odoo_version: "19.0"
runtime:
  compose_file: docker-compose.yml
postgres:
  host: localhost
  port: 5432
  user: odoo
  password_env: ODOO_DB_PASSWORD
backups:
  local_path: backups
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


# ---- ServiceResult model ----

def test_service_result_success_wraps_value():
    result = ServiceResult.success(42)
    assert result.ok is True
    assert result.value == 42
    assert result.error is None


def test_service_result_failure_wraps_error():
    result = ServiceResult.failure("something went wrong")
    assert result.ok is False
    assert result.value is None
    assert result.error == "something went wrong"


def test_service_result_success_can_wrap_none():
    result = ServiceResult.success(None)
    assert result.ok is True
    assert result.value is None


# ---- Result model construction ----

def test_backup_result_holds_backup_id():
    r = BackupResult(backup_id="staging_2026-01-01_000000")
    assert r.backup_id == "staging_2026-01-01_000000"


def test_restore_result_holds_backup_id():
    r = RestoreResult(backup_id="staging_2026-01-01_000000")
    assert r.backup_id == "staging_2026-01-01_000000"


def test_clone_result_holds_url():
    r = CloneResult(url="https://staging.example.com")
    assert r.url == "https://staging.example.com"


def test_deploy_result_holds_status_and_optional_backup_id():
    r = DeployResult(environment="production", status="success", backup_id="prod_2026")
    assert r.environment == "production"
    assert r.status == "success"
    assert r.backup_id == "prod_2026"


def test_deploy_result_backup_id_may_be_none():
    r = DeployResult(environment="staging", status="success", backup_id=None)
    assert r.backup_id is None


def test_doctor_report_reflects_ok_when_all_checks_pass():
    r = DoctorReport(project="demo", root="/p", config_path="/p/odooctl.yml", ok=True, checks=[])
    assert r.ok is True
    assert r.project == "demo"


def test_status_report_holds_environments():
    env = EnvironmentSummary(
        name="production",
        url="https://odoo.example.com",
        branch="main",
        commit="abc1234",
        image="registry/odoo:latest",
        odoo_status="running",
        postgres_status="running",
        latest_backup="unknown",
        last_deployment="unknown",
        last_deployment_backup="unknown",
        last_deployment_message=None,
        health_check="unknown",
        health_check_url="https://odoo.example.com/web/health",
    )
    r = StatusReport(project="demo", git_commit="abc1234", environments=[env])
    assert r.project == "demo"
    assert len(r.environments) == 1
    assert r.environments[0].name == "production"


# ---- ServiceContext ----

def test_service_context_wraps_project_context(tmp_path):
    config = tmp_path / "odooctl.yml"
    config.write_text(MINIMAL_CONFIG)
    ctx = ServiceContext.from_config_path(str(config))
    assert ctx.project.config.project.name == "demo"


def test_service_context_exposes_project_root(tmp_path):
    config = tmp_path / "odooctl.yml"
    config.write_text(MINIMAL_CONFIG)
    ctx = ServiceContext.from_config_path(str(config))
    assert ctx.project.root == tmp_path


# ---- project service: get_status ----

class _DummyCompose:
    def __init__(self, compose_file, **kwargs):
        pass

    def ps(self):
        return "odoo running\npostgres running"


class _DummyStore:
    def __init__(self, *args, **kwargs):
        pass

    def latest_deployment(self, environment):
        if environment == "production":
            return {
                "status": "success",
                "commit": "abc1234",
                "docker_image": "registry/odoo:latest",
                "backup": "production_2026",
                "message": None,
                "health_check_url": "https://odoo.example.com/web/health",
            }
        return None

    def latest_backup(self, environment):
        return None


def test_get_status_returns_status_report_for_one_environment(tmp_path, monkeypatch):
    config = tmp_path / "odooctl.yml"
    config.write_text(MINIMAL_CONFIG)
    ctx = ServiceContext.from_config_path(str(config))
    monkeypatch.setattr(project_svc, "DockerComposeAdapter", _DummyCompose)
    monkeypatch.setattr(project_svc, "MetadataStore", _DummyStore)
    monkeypatch.setattr(project_svc, "git_commit", lambda cwd=None: "feedbeef")

    report = project_svc.get_status(ctx, "production")

    assert isinstance(report, StatusReport)
    assert report.project == "demo"
    assert report.git_commit == "feedbeef"
    assert len(report.environments) == 1
    env = report.environments[0]
    assert env.name == "production"
    assert env.odoo_status == "running"
    assert env.postgres_status == "running"
    assert env.last_deployment == "success"
    assert env.last_deployment_backup == "production_2026"


def test_get_status_returns_all_environments_when_environment_is_none(tmp_path, monkeypatch):
    config = tmp_path / "odooctl.yml"
    config.write_text(MINIMAL_CONFIG)
    ctx = ServiceContext.from_config_path(str(config))
    monkeypatch.setattr(project_svc, "DockerComposeAdapter", _DummyCompose)
    monkeypatch.setattr(project_svc, "MetadataStore", _DummyStore)
    monkeypatch.setattr(project_svc, "git_commit", lambda cwd=None: None)

    report = project_svc.get_status(ctx)

    assert len(report.environments) == 2
    names = {e.name for e in report.environments}
    assert names == {"production", "staging"}


def test_get_status_marks_service_stopped_when_compose_reports_exit(tmp_path, monkeypatch):
    config = tmp_path / "odooctl.yml"
    config.write_text(MINIMAL_CONFIG)
    ctx = ServiceContext.from_config_path(str(config))

    class StoppedCompose(_DummyCompose):
        def ps(self):
            return "odoo exited (1)\npostgres running"

    monkeypatch.setattr(project_svc, "DockerComposeAdapter", StoppedCompose)
    monkeypatch.setattr(project_svc, "MetadataStore", _DummyStore)
    monkeypatch.setattr(project_svc, "git_commit", lambda cwd=None: None)

    report = project_svc.get_status(ctx, "production")

    assert report.environments[0].odoo_status == "stopped"


# ---- backup service: run_backup ----

def test_run_backup_returns_backup_result_with_environment_prefix(tmp_path, monkeypatch):
    config = tmp_path / "odooctl.yml"
    config.write_text(MINIMAL_CONFIG)
    ctx = ServiceContext.from_config_path(str(config))
    monkeypatch.setenv("ODOO_DB_PASSWORD", "secret")

    class FakePg:
        def __init__(self, cfg):
            pass
        def dump(self, db, path):
            Path(path).write_bytes(b"dump")

    class FakeFs:
        def archive(self, src, dst):
            Path(dst).write_bytes(b"tar")

    class FakeMeta:
        def __init__(self, root):
            pass
        def save_backup_manifest(self, backup_id, manifest):
            pass

    monkeypatch.setattr(backup_svc, "PostgresAdapter", FakePg)
    monkeypatch.setattr(backup_svc, "FilestoreAdapter", FakeFs)
    monkeypatch.setattr(backup_svc, "MetadataStore", FakeMeta)
    monkeypatch.setattr(backup_svc, "git_commit", lambda cwd=None: "abc123")

    result = backup_svc.run_backup(ctx, "production")

    assert isinstance(result, BackupResult)
    assert result.backup_id.startswith("production_")


def test_run_backup_raises_when_db_password_missing(tmp_path, monkeypatch):
    config = tmp_path / "odooctl.yml"
    config.write_text(MINIMAL_CONFIG)
    ctx = ServiceContext.from_config_path(str(config))
    monkeypatch.delenv("ODOO_DB_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="Missing required environment variable"):
        backup_svc.run_backup(ctx, "production")


# ---- restore service: run_restore ----

def test_run_restore_raises_when_no_backups_exist(tmp_path, monkeypatch):
    config = tmp_path / "odooctl.yml"
    config.write_text(MINIMAL_CONFIG)
    ctx = ServiceContext.from_config_path(str(config))

    with pytest.raises(RuntimeError, match="No backups found"):
        restore_svc.run_restore(ctx, "staging", "latest")


def test_run_restore_raises_on_missing_backup_dir(tmp_path, monkeypatch):
    config = tmp_path / "odooctl.yml"
    config.write_text(MINIMAL_CONFIG)
    ctx = ServiceContext.from_config_path(str(config))

    with pytest.raises(FileNotFoundError):
        restore_svc.run_restore(ctx, "staging", "staging_2026-01-01_000000")


# ---- clone service: run_clone ----

def test_run_clone_preview_returns_clone_result_with_target_url(tmp_path):
    config = tmp_path / "odooctl.yml"
    config.write_text(MINIMAL_CONFIG)
    (tmp_path / "docker-compose.yml").touch()
    ctx = ServiceContext.from_config_path(str(config))

    result = clone_svc.run_clone(ctx, "production", "staging", sanitize=True, preview=True)

    assert isinstance(result, CloneResult)
    assert result.url == "https://staging.example.com"


def test_run_clone_preview_is_side_effect_free(tmp_path, monkeypatch):
    config = tmp_path / "odooctl.yml"
    config.write_text(MINIMAL_CONFIG)
    (tmp_path / "docker-compose.yml").touch()
    ctx = ServiceContext.from_config_path(str(config))

    called = []
    monkeypatch.setattr(clone_svc, "PostgresAdapter", lambda *a, **k: called.append("pg"))
    monkeypatch.setattr(clone_svc, "FilestoreAdapter", lambda *a, **k: called.append("fs"))
    monkeypatch.setattr(clone_svc, "DockerComposeAdapter", lambda *a, **k: called.append("compose"))

    clone_svc.run_clone(ctx, "production", "staging", sanitize=True, preview=True)

    assert called == []


def test_run_clone_rejects_unconfigured_target(tmp_path):
    config = tmp_path / "odooctl.yml"
    config.write_text(MINIMAL_CONFIG.replace("    clone_from: production\n    sanitize: true\n", ""))
    ctx = ServiceContext.from_config_path(str(config))

    with pytest.raises(RuntimeError, match="not configured as a clone target"):
        clone_svc.run_clone(ctx, "production", "staging", sanitize=True, preview=True)


def test_run_clone_rejects_unsanitized_production_clone(tmp_path):
    config = tmp_path / "odooctl.yml"
    config.write_text(MINIMAL_CONFIG)
    ctx = ServiceContext.from_config_path(str(config))

    with pytest.raises(RuntimeError, match="without sanitization enabled"):
        clone_svc.run_clone(ctx, "production", "staging", sanitize=False, preview=True)
