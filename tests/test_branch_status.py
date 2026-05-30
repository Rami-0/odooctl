"""TDD tests for M9 branch status service."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from odooctl.config import OdooCtlConfig, load_config
from odooctl.services import branch as branch_svc
from odooctl.services.context import ServiceContext
from odooctl.services.models import BranchStatus


MINIMAL_CONFIG = """\
project:
  name: demo
  odoo_version: "19.0"
runtime:
  compose_file: docker-compose.yml
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
    promotes_to: production
"""

TIERED_CONFIG = """\
project:
  name: demo
  odoo_version: "19.0"
runtime:
  compose_file: docker-compose.yml
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
  staging:
    tier: staging
    branch: staging
    promotes_to: production
    domain: staging.example.com
    db_name: odoo_staging
    filestore_path: /srv/filestore/staging
    clone_from: production
    sanitize: true
  dev:
    tier: development
    branch: feature/x
    domain: dev.example.com
    db_name: odoo_dev
    filestore_path: /srv/filestore/dev
    clone_from: production
    sanitize: true
"""


def _make_ctx(tmp_path: Path, config_text: str) -> ServiceContext:
    cfg_path = tmp_path / "odooctl.yml"
    cfg_path.write_text(config_text)
    return ServiceContext.from_config_path(str(cfg_path), root=tmp_path)


def _make_run(mapping: dict):
    """Return a fake `run` that returns stdout from mapping or empty string."""
    def fake_run(args, check=True, cwd=None, **kwargs):
        key = tuple(args)
        response = mapping.get(key, "")
        return SimpleNamespace(stdout=response, returncode=0, stderr="", args=list(args))
    return fake_run


class _FakeMetaStore:
    def __init__(self, deployments: dict):
        self._deployments = deployments

    def latest_deployment(self, environment: str) -> dict | None:
        return self._deployments.get(environment)


# ─── BranchStatus model ───────────────────────────────────────────────────────

def test_branch_status_dataclass_fields():
    s = BranchStatus(
        environment="production",
        tier="production",
        branch="main",
        current_commit="abc1234",
        last_deployed_commit="abc1234",
        ahead=0,
        behind=0,
        drift="clean",
    )
    assert s.environment == "production"
    assert s.drift == "clean"


# ─── get_branch_statuses ─────────────────────────────────────────────────────

def test_branch_status_returns_one_entry_per_environment(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, MINIMAL_CONFIG)
    monkeypatch.setattr(branch_svc, "run", _make_run({}))
    monkeypatch.setattr(branch_svc, "MetadataStore", lambda root: _FakeMetaStore({}))

    statuses = branch_svc.get_branch_statuses(ctx)
    env_names = {s.environment for s in statuses}
    assert env_names == {"production", "staging"}


def test_branch_status_clean_when_commit_matches_deployed(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, MINIMAL_CONFIG)
    monkeypatch.setattr(branch_svc, "run", _make_run({
        ("git", "rev-parse", "--short", "main"): "abc1234",
        ("git", "rev-parse", "--short", "staging"): "def5678",
    }))
    monkeypatch.setattr(branch_svc, "MetadataStore", lambda root: _FakeMetaStore({
        "production": {"commit": "abc1234", "status": "success"},
        "staging": {"commit": "def5678", "status": "success"},
    }))

    statuses = branch_svc.get_branch_statuses(ctx)
    by_env = {s.environment: s for s in statuses}
    prod = by_env["production"]
    assert prod.drift == "clean"
    assert prod.current_commit == "abc1234"
    assert prod.last_deployed_commit == "abc1234"
    assert prod.ahead == 0
    assert prod.behind == 0


def test_branch_status_ahead_when_new_commits_on_branch(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, MINIMAL_CONFIG)
    monkeypatch.setattr(branch_svc, "run", _make_run({
        ("git", "rev-parse", "--short", "main"): "newHead",
        ("git", "rev-parse", "--short", "staging"): "def5678",
        # _git_count(deployed="abc1234", current="newHead")
        ("git", "rev-list", "--count", "abc1234..newHead"): "3",
        ("git", "rev-list", "--count", "newHead..abc1234"): "0",
        # staging is clean (current == deployed so _compute_drift returns early)
        ("git", "rev-list", "--count", "def5678..def5678"): "0",
    }))
    monkeypatch.setattr(branch_svc, "MetadataStore", lambda root: _FakeMetaStore({
        "production": {"commit": "abc1234"},
        "staging": {"commit": "def5678"},
    }))

    statuses = branch_svc.get_branch_statuses(ctx)
    by_env = {s.environment: s for s in statuses}
    prod = by_env["production"]
    assert prod.drift == "ahead"
    assert prod.ahead == 3
    assert prod.behind == 0


def test_branch_status_unknown_when_no_deployment_recorded(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, MINIMAL_CONFIG)
    monkeypatch.setattr(branch_svc, "run", _make_run({
        ("git", "rev-parse", "--short", "main"): "abc1234",
        ("git", "rev-parse", "--short", "staging"): "def5678",
    }))
    monkeypatch.setattr(branch_svc, "MetadataStore", lambda root: _FakeMetaStore({}))

    statuses = branch_svc.get_branch_statuses(ctx)
    by_env = {s.environment: s for s in statuses}
    assert by_env["production"].drift == "unknown"
    assert by_env["production"].last_deployed_commit is None


def test_branch_status_unknown_when_git_rev_parse_fails(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, MINIMAL_CONFIG)
    # empty stdout → _git_rev returns None
    monkeypatch.setattr(branch_svc, "run", _make_run({}))
    monkeypatch.setattr(branch_svc, "MetadataStore", lambda root: _FakeMetaStore({
        "production": {"commit": "abc1234"},
        "staging": {"commit": "def5678"},
    }))

    statuses = branch_svc.get_branch_statuses(ctx)
    by_env = {s.environment: s for s in statuses}
    assert by_env["production"].drift == "unknown"
    assert by_env["production"].current_commit is None


def test_branch_status_diverged_when_both_sides_have_unique_commits(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, MINIMAL_CONFIG)
    monkeypatch.setattr(branch_svc, "run", _make_run({
        ("git", "rev-parse", "--short", "main"): "newHead",
        ("git", "rev-parse", "--short", "staging"): "def5678",
        # _git_count(deployed="oldDeploy", current="newHead")
        ("git", "rev-list", "--count", "oldDeploy..newHead"): "2",
        ("git", "rev-list", "--count", "newHead..oldDeploy"): "1",
        # staging clean
        ("git", "rev-list", "--count", "def5678..def5678"): "0",
    }))
    monkeypatch.setattr(branch_svc, "MetadataStore", lambda root: _FakeMetaStore({
        "production": {"commit": "oldDeploy"},
        "staging": {"commit": "def5678"},
    }))

    statuses = branch_svc.get_branch_statuses(ctx)
    by_env = {s.environment: s for s in statuses}
    prod = by_env["production"]
    assert prod.drift == "diverged"
    assert prod.ahead == 2
    assert prod.behind == 1


def test_branch_status_behind_when_deployed_is_ahead_of_branch(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, MINIMAL_CONFIG)
    monkeypatch.setattr(branch_svc, "run", _make_run({
        ("git", "rev-parse", "--short", "main"): "currentHead",
        ("git", "rev-parse", "--short", "staging"): "def5678",
        # _git_count(deployed="deployedHead", current="currentHead")
        ("git", "rev-list", "--count", "deployedHead..currentHead"): "0",
        ("git", "rev-list", "--count", "currentHead..deployedHead"): "2",
        # staging clean
        ("git", "rev-list", "--count", "def5678..def5678"): "0",
    }))
    monkeypatch.setattr(branch_svc, "MetadataStore", lambda root: _FakeMetaStore({
        "production": {"commit": "deployedHead"},
        "staging": {"commit": "def5678"},
    }))

    statuses = branch_svc.get_branch_statuses(ctx)
    by_env = {s.environment: s for s in statuses}
    prod = by_env["production"]
    assert prod.drift == "behind"
    assert prod.ahead == 0
    assert prod.behind == 2


# ─── Tier inference ───────────────────────────────────────────────────────────

def test_branch_status_infers_production_tier_from_env_name(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, MINIMAL_CONFIG)  # no tier field
    monkeypatch.setattr(branch_svc, "run", _make_run({}))
    monkeypatch.setattr(branch_svc, "MetadataStore", lambda root: _FakeMetaStore({}))

    statuses = branch_svc.get_branch_statuses(ctx)
    by_env = {s.environment: s for s in statuses}
    assert by_env["production"].tier == "production"
    assert by_env["staging"].tier is None  # no tier set, not named "production"


def test_branch_status_uses_explicit_tier_from_config(tmp_path: Path, monkeypatch):
    ctx = _make_ctx(tmp_path, TIERED_CONFIG)
    monkeypatch.setattr(branch_svc, "run", _make_run({}))
    monkeypatch.setattr(branch_svc, "MetadataStore", lambda root: _FakeMetaStore({}))

    statuses = branch_svc.get_branch_statuses(ctx)
    by_env = {s.environment: s for s in statuses}
    assert by_env["production"].tier == "production"
    assert by_env["staging"].tier == "staging"
    assert by_env["dev"].tier == "development"


# ─── Config: is_protected / promotes_to ──────────────────────────────────────

def test_is_protected_defaults_production_name_to_true(tmp_path: Path):
    cfg_path = tmp_path / "odooctl.yml"
    cfg_path.write_text(MINIMAL_CONFIG)
    cfg = load_config(cfg_path)
    assert cfg.is_protected("production") is True
    assert cfg.is_protected("staging") is False


def test_is_protected_respects_explicit_true_flag(tmp_path: Path):
    import yaml
    data = yaml.safe_load(TIERED_CONFIG)
    data["environments"]["staging"]["protected"] = True
    cfg = OdooCtlConfig.model_validate(data)
    assert cfg.is_protected("staging") is True


def test_is_protected_explicit_false_overrides_production_name(tmp_path: Path):
    import yaml
    data = yaml.safe_load(MINIMAL_CONFIG)
    data["environments"]["production"]["protected"] = False
    cfg = OdooCtlConfig.model_validate(data)
    assert cfg.is_protected("production") is False


def test_promotes_to_must_reference_existing_environment(tmp_path: Path):
    import yaml
    data = yaml.safe_load(MINIMAL_CONFIG)
    data["environments"]["staging"]["promotes_to"] = "nonexistent"
    with pytest.raises(Exception, match="promotes_to 'nonexistent' is not defined"):
        OdooCtlConfig.model_validate(data)


def test_promotes_to_cannot_reference_self(tmp_path: Path):
    import yaml
    data = yaml.safe_load(MINIMAL_CONFIG)
    data["environments"]["staging"]["promotes_to"] = "staging"
    with pytest.raises(Exception, match="cannot promotes_to itself"):
        OdooCtlConfig.model_validate(data)


def test_tier_field_accepted_in_config(tmp_path: Path):
    cfg_path = tmp_path / "odooctl.yml"
    cfg_path.write_text(TIERED_CONFIG)
    cfg = load_config(cfg_path)
    assert cfg.environments["production"].tier == "production"
    assert cfg.environments["staging"].tier == "staging"
    assert cfg.environments["dev"].tier == "development"


def test_auto_deploy_defaults_to_false(tmp_path: Path):
    cfg_path = tmp_path / "odooctl.yml"
    cfg_path.write_text(MINIMAL_CONFIG)
    cfg = load_config(cfg_path)
    assert cfg.environments["production"].auto_deploy is False
