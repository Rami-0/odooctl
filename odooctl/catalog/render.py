"""Render a StackTemplate into an odooctl.yml scaffold config dict."""
from __future__ import annotations

from odooctl.catalog.schema import StackTemplate


def render_stack_template(template: StackTemplate, project_name: str) -> dict:
    """Return an odooctl.yml config dict for a greenfield project from a catalog StackTemplate.

    Secrets are referenced by env-var name only — never inlined.
    """
    db_name = f"{project_name}_prod"
    return {
        "project": {
            "name": project_name,
            "odoo_version": template.odoo_version,
        },
        "runtime": {
            "type": "docker_compose",
            "compose_file": "docker-compose.yml",
            "reverse_proxy": "traefik",
        },
        "postgres": {
            "host": "localhost",
            "port": 5432,
            "user": "odoo",
            "password_env": "ODOO_DB_PASSWORD",
            "service": "db",
        },
        "odoo": {
            "image": template.odoo_image,
            "service": "odoo",
            "addons_paths": ["/mnt/extra-addons"],
        },
        "backups": {
            "local_path": "./backups",
        },
        "environments": {
            "production": {
                "branch": "main",
                "domain": "odoo.example.com",
                "db_name": db_name,
                "filestore_path": f"/var/lib/odoo/filestore/{db_name}",
            }
        },
    }
