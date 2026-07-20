"""Tests for the read-only importer detector.

Safety contract: detect_from_compose must never run subprocess commands,
write files, restart/stop/start containers, or access the Docker daemon.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from odooctl.importer.detect import detect_from_compose
from odooctl.importer.models import DetectedCompose

# Vendored copy of the odoo19-community-staging experiment's compose file —
# experiments/ is untracked, so the suite must not depend on it.
STAGING_COMPOSE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "odoo19-community-staging-compose.yml"
)

MINIMAL_COMPOSE = """\
services:
  db:
    image: postgres:17
    environment:
      POSTGRES_DB: postgres
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: ${ODOO_DB_PASSWORD:-odoo}
    volumes:
      - postgres-data:/var/lib/postgresql/data

  odoo:
    image: odoo:19.0
    environment:
      HOST: db
      USER: odoo
      PASSWORD: ${ODOO_DB_PASSWORD:-odoo}
    ports:
      - "18069:8069"
    volumes:
      - odoo-data:/var/lib/odoo
      - ./addons:/mnt/extra-addons

volumes:
  postgres-data:
  odoo-data:
"""


def test_detect_finds_odoo_service(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(MINIMAL_COMPOSE)

    result = detect_from_compose(compose_file)

    assert result.odoo_service == "odoo"
    assert result.odoo_image == "odoo:19.0"


def test_detect_finds_postgres_service(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(MINIMAL_COMPOSE)

    result = detect_from_compose(compose_file)

    assert result.postgres_service == "db"
    assert "postgres" in result.postgres_image


def test_detect_extracts_http_port(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(MINIMAL_COMPOSE)

    result = detect_from_compose(compose_file)

    assert result.http_port == 18069


def test_detect_references_password_by_env_var_name(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(MINIMAL_COMPOSE)

    result = detect_from_compose(compose_file)

    # Must reference the env var name, never the literal secret value
    assert result.db_password_ref is not None
    assert "ODOO_DB_PASSWORD" in result.db_password_ref


def test_detect_extracts_addons_paths(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(MINIMAL_COMPOSE)

    result = detect_from_compose(compose_file)

    assert "/mnt/extra-addons" in result.addons_paths


def test_detect_finds_filestore_volume(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(MINIMAL_COMPOSE)

    result = detect_from_compose(compose_file)

    assert result.filestore_volume == "odoo-data"
    assert result.filestore_path == "/var/lib/odoo"


def test_detect_does_not_inline_secret_values(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(MINIMAL_COMPOSE)

    result = detect_from_compose(compose_file)

    # db_password_ref must be an env var name reference, not a raw value
    assert result.db_password_ref is not None
    assert not result.db_password_ref.startswith("$")  # not a raw interpolation
    assert result.db_password_ref == result.db_password_ref.upper()  # env var convention


def test_detect_reads_staging_compose_file() -> None:
    """Verify detection works on the real staging compose fixture."""
    result = detect_from_compose(STAGING_COMPOSE)

    assert result.odoo_service == "odoo"
    assert result.postgres_service == "db"
    assert result.http_port == 18069
    assert result.odoo_image == "odoo:19.0"


def test_detect_compose_path_is_recorded(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(MINIMAL_COMPOSE)

    result = detect_from_compose(compose_file)

    assert result.compose_path == compose_file


def test_detect_raises_on_missing_odoo_service(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        "services:\n  myapp:\n    image: nginx:latest\n"
    )

    with pytest.raises(ValueError, match="No Odoo service detected"):
        detect_from_compose(compose_file)


def test_detect_db_user_from_environment(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(MINIMAL_COMPOSE)

    result = detect_from_compose(compose_file)

    assert result.db_user == "odoo"


def test_detect_db_host_from_environment(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(MINIMAL_COMPOSE)

    result = detect_from_compose(compose_file)

    assert result.db_host == "db"


def test_detect_returns_detected_compose_instance(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(MINIMAL_COMPOSE)

    result = detect_from_compose(compose_file)

    assert isinstance(result, DetectedCompose)


def test_detect_no_port_when_none_published(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        """\
services:
  db:
    image: postgres:17
  odoo:
    image: odoo:17.0
    environment:
      HOST: db
      USER: odoo
      PASSWORD: ${ODOO_DB_PASSWORD:-odoo}
"""
    )

    result = detect_from_compose(compose_file)

    assert result.http_port is None


def test_detect_env_list_format(tmp_path: Path) -> None:
    """Compose files can use list form for environment variables."""
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        """\
services:
  db:
    image: postgres:16
  odoo:
    image: odoo:16.0
    environment:
      - HOST=db
      - USER=odoo
      - PASSWORD=${ODOO_DB_PASSWORD:-changeme}
    ports:
      - "8069:8069"
    volumes:
      - odoo-data:/var/lib/odoo
volumes:
  odoo-data:
"""
    )

    result = detect_from_compose(compose_file)

    assert result.db_host == "db"
    assert result.db_user == "odoo"
    assert result.db_password_ref == "ODOO_DB_PASSWORD"
    assert result.http_port == 8069
