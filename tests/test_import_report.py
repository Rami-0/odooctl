"""Tests for import preview report builder."""
from __future__ import annotations

from pathlib import Path

import yaml

from odooctl.importer.detect import detect_from_compose
from odooctl.importer.models import ImportPreviewReport
from odooctl.importer.report import build_preview_report, render_preview_text

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


def test_build_preview_report_returns_instance(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(MINIMAL_COMPOSE)
    detected = detect_from_compose(compose_file)

    report = build_preview_report(detected, project_name="myproject")

    assert isinstance(report, ImportPreviewReport)


def test_preview_report_generated_config_is_valid_yaml(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(MINIMAL_COMPOSE)
    detected = detect_from_compose(compose_file)

    report = build_preview_report(detected, project_name="myproject")

    cfg = yaml.safe_load(report.generated_config)
    assert isinstance(cfg, dict)
    assert "project" in cfg
    assert "environments" in cfg


def test_preview_report_project_name_in_config(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(MINIMAL_COMPOSE)
    detected = detect_from_compose(compose_file)

    report = build_preview_report(detected, project_name="myproject")

    cfg = yaml.safe_load(report.generated_config)
    assert cfg["project"]["name"] == "myproject"


def test_preview_report_contains_env_var_references_not_inline_secret(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(MINIMAL_COMPOSE)
    detected = detect_from_compose(compose_file)

    report = build_preview_report(detected, project_name="myproject")

    # Generated config must reference env var names, never inline secret values
    assert "ODOO_DB_PASSWORD" in report.generated_config
    # Must not contain literal secret assignment (only _env references)
    assert "password: " not in report.generated_config


def test_preview_report_includes_odoo_image(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(MINIMAL_COMPOSE)
    detected = detect_from_compose(compose_file)

    report = build_preview_report(detected, project_name="myproject")

    cfg = yaml.safe_load(report.generated_config)
    assert cfg["odoo"]["image"] == "odoo:19.0"


def test_preview_report_includes_addons_paths(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(MINIMAL_COMPOSE)
    detected = detect_from_compose(compose_file)

    report = build_preview_report(detected, project_name="myproject")

    cfg = yaml.safe_load(report.generated_config)
    assert "/mnt/extra-addons" in cfg["odoo"].get("addons_paths", [])


def test_render_preview_text_includes_key_detected_fields(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(MINIMAL_COMPOSE)
    detected = detect_from_compose(compose_file)
    report = build_preview_report(detected, project_name="myproject")

    text = render_preview_text(report)

    assert "odoo" in text.lower()
    assert "18069" in text
    assert "db" in text.lower()


def test_render_preview_text_shows_env_var_not_secret(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(MINIMAL_COMPOSE)
    detected = detect_from_compose(compose_file)
    report = build_preview_report(detected, project_name="myproject")

    text = render_preview_text(report)

    assert "ODOO_DB_PASSWORD" in text


def test_preview_report_odoo_version_inferred_from_image(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(MINIMAL_COMPOSE)
    detected = detect_from_compose(compose_file)

    report = build_preview_report(detected, project_name="myproject")

    cfg = yaml.safe_load(report.generated_config)
    assert cfg["project"]["odoo_version"] == "19.0"


def test_preview_report_has_postgres_section(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(MINIMAL_COMPOSE)
    detected = detect_from_compose(compose_file)

    report = build_preview_report(detected, project_name="myproject")

    cfg = yaml.safe_load(report.generated_config)
    assert "postgres" in cfg
    assert cfg["postgres"]["password_env"] == "ODOO_DB_PASSWORD"
