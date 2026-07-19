"""M14 web UI and API tests — restore points and DR drill affordances."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from odooctl.security import tokens  # noqa: E402

_DIST = Path(__file__).parent.parent / "odooctl" / "web" / "dist"

TEST_KEY = "test-m14-key-789-0123456789abcdef0123"

MINIMAL_CONFIG = """\
project:
  name: m14-test-project
  odoo_version: "19.0"
runtime:
  compose_file: docker-compose.yml
postgres:
  password_env: ODOO_DB_PASSWORD
odoo:
  image: odoo:19.0
environments:
  production:
    branch: main
    domain: prod.m14.local
    port: 8069
    db_name: m14_prod
    filestore_path: ./filestore/production
  staging:
    branch: staging
    domain: staging.m14.local
    port: 8070
    db_name: m14_staging
    filestore_path: ./filestore/staging
    clone_from: production
    sanitize: true
"""


@pytest.fixture
def project_dir(tmp_path):
    (tmp_path / "odooctl.yml").write_text(MINIMAL_CONFIG)
    return tmp_path


@pytest.fixture
def fake_registry(project_dir):
    from odooctl.registry import Registry, RegisteredProject

    return Registry(
        path=project_dir / "registry.toml",
        active="m14-test-project",
        projects={
            "m14-test-project": RegisteredProject(
                name="m14-test-project",
                path=project_dir,
                config="odooctl.yml",
            )
        },
    )


@pytest.fixture
def api_client(fake_registry):
    from odooctl.api.app import create_app

    app = create_app(
        api_key=TEST_KEY,
        registry_loader=lambda: fake_registry,
        allowed_hosts=["*"],
    )
    return TestClient(app, raise_server_exceptions=False)


def _operator_token():
    return tokens.mint(TEST_KEY, action="api", environment="*", project="*", ttl_seconds=300, roles=["operator"])


def _make_backup(backups_root: Path, env: str) -> str:
    backup_id = f"{env}_2026-05-31_100000"
    d = backups_root / backup_id
    d.mkdir(parents=True)
    (d / "db.dump").write_bytes(b"dbdata")
    (d / "filestore.tar").write_bytes(b"fsdata")
    db_hash = hashlib.sha256(b"dbdata").hexdigest()
    fs_hash = hashlib.sha256(b"fsdata").hexdigest()
    manifest = {
        "backup_id": backup_id,
        "project": "m14-test-project",
        "environment": env,
        "timestamp": "2026-05-31_100000",
        "db_name": f"{env}_db",
        "odoo_version": "19.0",
        "backup_mode": "full",
        "checksums": {"db_dump": db_hash, "filestore": fs_hash},
    }
    (d / "manifest.json").write_text(json.dumps(manifest))
    return backup_id


# ---------------------------------------------------------------------------
# API: /projects/{project}/restore-points
# ---------------------------------------------------------------------------

def test_restore_points_endpoint_exists(api_client, project_dir):
    tok = _operator_token()
    resp = api_client.get(
        "/projects/m14-test-project/restore-points",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "restore_points" in data


def test_restore_points_endpoint_returns_list(api_client, project_dir):
    backups_root = project_dir / "backups"
    backups_root.mkdir()
    _make_backup(backups_root, "production")

    tok = _operator_token()
    resp = api_client.get(
        "/projects/m14-test-project/restore-points",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp.status_code == 200
    points = resp.json()["restore_points"]
    assert len(points) == 1
    assert points[0]["backup_id"] == "production_2026-05-31_100000"
    assert points[0]["integrity"] == "ok"


def test_restore_points_endpoint_filters_by_environment(api_client, project_dir):
    backups_root = project_dir / "backups"
    backups_root.mkdir()
    _make_backup(backups_root, "production")
    _make_backup(backups_root, "staging")

    tok = _operator_token()
    resp = api_client.get(
        "/projects/m14-test-project/restore-points?environment=staging",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp.status_code == 200
    points = resp.json()["restore_points"]
    assert all(p["environment"] == "staging" for p in points)


def test_restore_points_endpoint_requires_auth(api_client):
    resp = api_client.get("/projects/m14-test-project/restore-points")
    assert resp.status_code == 401


def test_restore_points_response_has_integrity_field(api_client, project_dir):
    backups_root = project_dir / "backups"
    backups_root.mkdir()
    _make_backup(backups_root, "production")

    tok = _operator_token()
    resp = api_client.get(
        "/projects/m14-test-project/restore-points",
        headers={"Authorization": f"Bearer {tok}"},
    )
    points = resp.json()["restore_points"]
    assert len(points) > 0
    assert "integrity" in points[0]
    assert "timestamp" in points[0]
    assert "environment" in points[0]


# ---------------------------------------------------------------------------
# SPA content — restore points and DR drill affordances
# ---------------------------------------------------------------------------

def test_app_js_mentions_restore_points():
    content = (_DIST / "app.js").read_text()
    assert "restore" in content.lower()
    assert "point" in content.lower() or "restore-points" in content


def test_app_js_has_dr_drill_affordance():
    content = (_DIST / "app.js").read_text()
    assert "dr" in content.lower() or "drill" in content.lower()


def test_app_js_calls_restore_points_endpoint():
    content = (_DIST / "app.js").read_text()
    assert "restore-points" in content


def test_app_js_has_integrity_display():
    content = (_DIST / "app.js").read_text()
    assert "integrity" in content
