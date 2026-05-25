from __future__ import annotations

from pathlib import Path

from odooctl.commands import github_actions


def test_render_workflow_contains_deploy_job():
    content = github_actions.render_workflow(["qa", "production"], default_branch="release")
    assert "workflow_dispatch" in content
    assert "- qa" in content
    assert "- production" in content
    assert "default: release" in content
    assert "odooctl validate" in content
    assert "odooctl deploy ${{ inputs.environment }} --branch ${{ inputs.branch }}" in content


def test_run_writes_default_workflow(tmp_path: Path):
    config = tmp_path / "odooctl.yml"
    config.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nenvironments:\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: demo_staging\n    filestore_path: /tmp/fs\nodoo:\n  image: odoo:19\n"""
    )
    output = tmp_path / ".github" / "workflows" / "odooctl-deploy.yml"

    rendered = github_actions.run(config=str(config), output=str(output))

    assert output.exists()
    content = output.read_text()
    assert content == rendered
    assert "actions/checkout@v4" in content
    assert "odooctl validate" in content
