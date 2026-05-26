from __future__ import annotations

from pathlib import Path

from odooctl.context import ProjectContext


def write_config(root: Path) -> Path:
    config = root / "nested" / "odooctl.yml"
    config.parent.mkdir()
    config.write_text(
        """project:\n  name: demo\n  odoo_version: \"19.0\"\nruntime:\n  compose_file: docker-compose.yml\nbackups:\n  local_path: backups\nsanitation: {}\nenvironments:\n  staging:\n    branch: staging\n    domain: staging.example.com\n    db_name: odoo_staging\n    filestore_path: filestore/odoo_staging\nodoo:\n  image: registry/odoo:latest\n  config_path: odoo.conf\nsanitization:\n  sql_files:\n    - .sanitize/staging.sql\n"""
    )
    return config


def test_project_context_roots_relative_paths_at_config_directory(tmp_path: Path):
    config = write_config(tmp_path)

    ctx = ProjectContext.from_config_path(config)

    assert ctx.root == config.parent.resolve()
    assert ctx.config_path == config.resolve()
    assert ctx.compose_file == (config.parent / "docker-compose.yml").resolve()
    assert ctx.backups_dir == (config.parent / "backups").resolve()
    assert ctx.odoo_config_path == (config.parent / "odoo.conf").resolve()
    assert ctx.sanitization_sql_files() == [(config.parent / ".sanitize" / "staging.sql").resolve()]
    assert ctx.state_dir == config.parent / ".odooctl"


def test_project_context_can_use_explicit_project_root(tmp_path: Path):
    config = write_config(tmp_path)
    root = tmp_path / "project-root"
    root.mkdir()

    ctx = ProjectContext.from_config_path(config, root=root)

    assert ctx.root == root.resolve()
    assert ctx.compose_file == (root / "docker-compose.yml").resolve()
