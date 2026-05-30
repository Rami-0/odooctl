"""Import preview report builder.

Safety contract: generated_config must never contain inline secret values.
Secrets are always referenced by env-var name only.
"""
from __future__ import annotations

import yaml

from odooctl.importer.models import DetectedCompose, ImportPreviewReport


def build_preview_report(
    detected: DetectedCompose,
    project_name: str,
) -> ImportPreviewReport:
    """Build a preview report with a generated odooctl.yml. Does not write files."""
    warnings: list[str] = []

    if not detected.db_password_ref:
        warnings.append(
            "Could not determine DB password env var reference; "
            "using placeholder 'ODOO_DB_PASSWORD'. Update before deploying."
        )

    generated_config = _generate_config(detected, project_name)

    return ImportPreviewReport(
        project_name=project_name,
        compose_path=detected.compose_path,
        detected=detected,
        warnings=warnings,
        generated_config=generated_config,
    )


def _infer_odoo_version(image: str) -> str:
    """Extract a semver-style tag from an Odoo image reference."""
    if ":" in image:
        tag = image.split(":")[-1]
        if tag and tag[0].isdigit() and "." in tag:
            return tag
    return "17.0"


def _generate_config(detected: DetectedCompose, project_name: str) -> str:
    """Produce an odooctl.yml YAML string from detection results.

    Safety: only env-var name references appear for secrets, never inline values.
    """
    password_env = detected.db_password_ref or "ODOO_DB_PASSWORD"
    db_user = detected.db_user or "odoo"
    db_host = detected.db_host or detected.postgres_service or "db"
    db_name = detected.db_name_candidates[0] if detected.db_name_candidates else "odoo"

    filestore_path = f"{detected.filestore_path}/filestore/{db_name}"

    env_block: dict = {
        "branch": "main",
        "domain": "odoo.example.com",
        "db_name": db_name,
        "filestore_path": filestore_path,
    }
    if detected.filestore_volume:
        env_block["filestore_volume"] = detected.filestore_volume
    if detected.http_port:
        env_block["port"] = detected.http_port

    odoo_block: dict = {
        "image": detected.odoo_image,
        "service": detected.odoo_service,
    }
    if detected.addons_paths:
        odoo_block["addons_paths"] = detected.addons_paths

    cfg: dict = {
        "project": {
            "name": project_name,
            "odoo_version": _infer_odoo_version(detected.odoo_image),
        },
        "runtime": {
            "type": "docker_compose",
            "compose_file": detected.compose_path.name,
        },
        "postgres": {
            "host": db_host,
            "port": 5432,
            "user": db_user,
            "password_env": password_env,
            "service": detected.postgres_service or "db",
        },
        "odoo": odoo_block,
        "backups": {
            "local_path": "./backups",
        },
        "environments": {
            "production": env_block,
        },
    }

    return yaml.dump(cfg, default_flow_style=False, sort_keys=False)


def render_preview_text(report: ImportPreviewReport) -> str:
    """Render a human-readable import preview (does not write files)."""
    d = report.detected
    lines: list[str] = [
        "Import Preview",
        "==============",
    ]

    if report.warnings:
        lines.append("Warnings:")
        for w in report.warnings:
            lines.append(f"  ! {w}")
        lines.append("")

    lines += [
        f"Compose file  : {d.compose_path}",
        f"Odoo service  : {d.odoo_service} (image: {d.odoo_image})",
        f"Postgres      : {d.postgres_service} (image: {d.postgres_image})",
        f"HTTP port     : {d.http_port}",
        f"DB host       : {d.db_host}",
        f"DB user       : {d.db_user}",
        f"DB password   : <env:{d.db_password_ref}>",
        f"DB candidates : {d.db_name_candidates}",
        f"Addons paths  : {d.addons_paths}",
        f"Filestore vol : {d.filestore_volume}",
        f"Filestore path: {d.filestore_path}",
        "",
        "Generated odooctl.yml:",
        "----------------------",
        report.generated_config,
    ]

    return "\n".join(lines)
