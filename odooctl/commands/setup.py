"""odooctl setup — scaffold a greenfield Odoo project.

Generates a starter odooctl.yml for a brand-new project that does not yet
have a running deployment. For importing an existing deployment, use
'odooctl import' instead.

Usage:
    odooctl setup                            # interactive wizard
    odooctl setup --yes --stack odoo-19-community --name myproject
"""
from __future__ import annotations

from pathlib import Path

import yaml
import typer

from odooctl.utils.logging import success, warn


KNOWN_STACKS: dict[str, dict[str, str]] = {
    "odoo-19-community": {"odoo_version": "19.0", "image": "odoo:19.0"},
    "odoo-17-community": {"odoo_version": "17.0", "image": "odoo:17.0"},
    "odoo-16-community": {"odoo_version": "16.0", "image": "odoo:16.0"},
}

_DEFAULT_STACK = "odoo-19-community"


def scaffold_project(
    project_name: str = "my-odoo-project",
    stack: str = _DEFAULT_STACK,
    output_path: Path = Path("odooctl.yml"),
    force: bool = False,
) -> None:
    """Write a starter odooctl.yml for a greenfield project.

    Raises FileExistsError if output_path exists and force is False.
    Secrets are referenced by env-var name only, never inlined.
    """
    if output_path.exists() and not force:
        raise FileExistsError(
            f"{output_path} already exists. "
            "Pass force=True (or --force on the CLI) to overwrite."
        )

    stack_info = KNOWN_STACKS.get(stack, KNOWN_STACKS[_DEFAULT_STACK])
    db_name = f"{project_name}_prod"

    cfg: dict = {
        "project": {
            "name": project_name,
            "odoo_version": stack_info["odoo_version"],
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
            "image": stack_info["image"],
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

    output_path.write_text(yaml.dump(cfg, default_flow_style=False, sort_keys=False))


def run(
    yes: bool = False,
    stack: str | None = None,
    name: str | None = None,
    output: Path = Path("odooctl.yml"),
    force: bool = False,
) -> None:
    """Interactive wizard to scaffold a greenfield Odoo project."""
    if yes:
        project_name = name or "my-odoo-project"
        chosen_stack = stack or _DEFAULT_STACK
    else:
        project_name = name or typer.prompt("Project name", default="my-odoo-project")
        stack_options = ", ".join(KNOWN_STACKS.keys())
        chosen_stack = stack or typer.prompt(
            f"Stack [{stack_options}]",
            default=_DEFAULT_STACK,
        )

    try:
        scaffold_project(
            project_name=project_name,
            stack=chosen_stack,
            output_path=output,
            force=force,
        )
    except FileExistsError as exc:
        raise typer.BadParameter(str(exc)) from exc

    success(f"Scaffolded {output} for project '{project_name}' (stack: {chosen_stack})")
    warn(
        "Update domains, db names, filestore paths, and environment variable "
        "names in the generated odooctl.yml before running 'odooctl deploy'."
    )
