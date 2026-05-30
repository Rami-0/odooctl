"""Data models for import detection and preview reports."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DetectedCompose:
    """Read-only snapshot of a detected Docker Compose Odoo deployment.

    Safety contract: no secret values may appear in any field.
    Passwords and tokens must be stored as env-var name references only.
    """

    compose_path: Path
    odoo_service: str
    odoo_image: str
    postgres_service: str
    postgres_image: str
    http_port: int | None
    db_host: str | None
    db_user: str | None
    # Env-var name reference for the DB password — never the literal value.
    db_password_ref: str | None
    db_name_candidates: list[str] = field(default_factory=list)
    addons_paths: list[str] = field(default_factory=list)
    filestore_volume: str | None = None
    filestore_path: str = "/var/lib/odoo"
    odoo_conf_settings: dict[str, str] = field(default_factory=dict)
    workers: int | None = None
    proxy_mode: bool | None = None
    dbfilter: str | None = None


@dataclass
class ImportPreviewReport:
    """Preview report produced by build_preview_report(); not yet written to disk.

    Safety contract: generated_config must not contain inline secret values.
    """

    project_name: str
    compose_path: Path
    detected: DetectedCompose
    warnings: list[str]
    # YAML text that will be written to odooctl.yml on adoption.
    generated_config: str
