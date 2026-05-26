from __future__ import annotations

from pathlib import Path

from odooctl.commands import github_actions


def test_render_workflow_contains_deploy_job():
    content = github_actions.render_workflow({"qa": "qa", "production": "main"}, default_branch="release")
    assert "workflow_dispatch" in content
    assert "- qa" in content
    assert "- production" in content
    assert "default: release" in content
    assert "odooctl validate --config odooctl.yml" in content
    assert 'qa) expected_branch="qa" ;;' in content
    assert 'production) expected_branch="main" ;;' in content
    assert "is not allowed for environment" in content
    assert "odooctl deploy ${{ inputs.environment }} --branch ${{ inputs.branch }} --config odooctl.yml" in content


def test_render_workflow_guards_branch_before_checkout():
    content = github_actions.render_workflow({"staging": "staging", "production": "main"})
    assert content.index("Enforce branch/environment mapping") < content.index("actions/checkout@v4")
    assert 'staging) expected_branch="staging" ;;' in content

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
