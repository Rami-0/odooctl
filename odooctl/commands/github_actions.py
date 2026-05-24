from __future__ import annotations

from pathlib import Path

import typer

from odooctl.config import load_config
from odooctl.utils.logging import success

WORKFLOW_FILENAME = "odooctl-deploy.yml"


def render_workflow() -> str:
    return """name: odooctl deploy

on:
  workflow_dispatch:
    inputs:
      environment:
        description: Target environment
        required: true
        type: choice
        options:
          - staging
          - production
      branch:
        description: Git branch to deploy
        required: true
        default: main
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
          ODOO_DB_PASSWORD: ${{ secrets.ODOO_DB_PASSWORD }}
        run: |
          odooctl deploy ${{ inputs.environment }} --branch ${{ inputs.branch }}
"""


def run(config: str = "odooctl.yml", output: str = f".github/workflows/{WORKFLOW_FILENAME}", dry_run: bool = False, force: bool = False) -> str:
    load_config(config)
    content = render_workflow()
    path = Path(output)
    if dry_run:
        return content
    if path.exists() and not force:
        raise typer.BadParameter(f"{output} already exists; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    success(f"Created {output}")
    return content
