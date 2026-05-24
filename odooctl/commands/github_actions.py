from __future__ import annotations

from pathlib import Path

import typer

from odooctl.config import load_config
from odooctl.utils.logging import success

WORKFLOW_FILENAME = "odooctl-deploy.yml"


def render_workflow(environment_names: list[str] | None = None, default_branch: str = "main") -> str:
    environment_names = environment_names or ["staging", "production"]
    options = "\n".join(f"          - {name}" for name in environment_names)
    return f"""name: odooctl deploy

on:
  workflow_dispatch:
    inputs:
      environment:
        description: Target environment
        required: true
        type: choice
        options:
{options}
      branch:
        description: Git branch to deploy
        required: true
        default: {default_branch}
        type: string

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install odooctl
        run: pip install .
      - name: Deploy
        env:
          ODOO_DB_PASSWORD: ${{{{ secrets.ODOO_DB_PASSWORD }}}}
        run: |
          odooctl deploy ${{{{ inputs.environment }}}} --branch ${{{{ inputs.branch }}}}
"""


def run(config: str = "odooctl.yml", output: str = f".github/workflows/{WORKFLOW_FILENAME}", dry_run: bool = False, force: bool = False) -> str:
    parsed = load_config(config)
    environment_names = sorted(parsed.environments)
    default_branch = parsed.environments.get("production", next(iter(parsed.environments.values()))).branch
    content = render_workflow(environment_names, default_branch)
    path = Path(output)
    if dry_run:
        return content
    if path.exists() and not force:
        raise typer.BadParameter(f"{output} already exists; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    success(f"Created {output}")
    return content
