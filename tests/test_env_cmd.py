from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from odooctl.main import app

runner = CliRunner()


def _write_config(root: Path) -> Path:
    config = root / "odooctl.yml"
    config.write_text(
        """project:
  name: acme
  odoo_version: "19.0"
runtime:
  compose_file: docker-compose.yml
environments:
  production:
    stack: prod
    branch: main
    scheme: http
    domain: localhost
    port: 18069
    db_name: acme_prod
    filestore_path: /var/lib/odoo/filestore/acme_prod
    filestore_volume: odoo-data
    db_selector: true
    update_modules: [base]
odoo:
  image: odoo:19.0
"""
    )
    return config


def test_env_list_and_show_json(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo)

    list_result = runner.invoke(app, ["--project-dir", str(repo), "env", "list", "--json"])
    assert list_result.exit_code == 0, list_result.output
    assert '"production"' in list_result.output
    assert '"db_name": "acme_prod"' in list_result.output

    show_result = runner.invoke(app, ["--project-dir", str(repo), "env", "show", "production", "--json"])
    assert show_result.exit_code == 0, show_result.output
    assert '"domain": "localhost"' in show_result.output


def test_env_create_writes_valid_config_and_provisions_with_clone(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    config = _write_config(repo)
    calls = []

    def fake_clone(source, target, sanitize, config_path, *args, **kwargs):
        calls.append((source, target, sanitize, Path(config_path)))
        return "http://localhost:18069"

    monkeypatch.setattr("odooctl.commands.env.clone_cmd.execute", fake_clone)

    result = runner.invoke(
        app,
        [
            "--project-dir",
            str(repo),
            "env",
            "create",
            "qa",
            "--clone-from",
            "production",
            "--branch",
            "qa",
            "--domain",
            "localhost",
            "--scheme",
            "http",
            "--port",
            "18069",
            "--db-name",
            "acme_qa",
            "--db-selector",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [("production", "qa", True, config)]
    data = yaml.safe_load(config.read_text())
    qa = data["environments"]["qa"]
    assert qa["clone_from"] == "production"
    assert qa["db_name"] == "acme_qa"
    assert qa["filestore_path"] == "/var/lib/odoo/filestore/acme_qa"
    assert qa["filestore_volume"] == "odoo-data"
    assert qa["db_selector"] is True

    validate = runner.invoke(app, ["--project-dir", str(repo), "validate"])
    assert validate.exit_code == 0, validate.output


def test_env_create_can_skip_provision(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    config = _write_config(repo)
    monkeypatch.setattr("odooctl.commands.env.clone_cmd.execute", lambda *a, **k: (_ for _ in ()).throw(AssertionError("unexpected clone")))

    result = runner.invoke(
        app,
        [
            "--project-dir",
            str(repo),
            "env",
            "create",
            "dev",
            "--clone-from",
            "production",
            "--domain",
            "dev.example.com",
            "--no-provision",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "dev" in yaml.safe_load(config.read_text())["environments"]


def test_env_destroy_refuses_production_and_removes_non_production(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    config = _write_config(repo)
    data = yaml.safe_load(config.read_text())
    data["environments"]["qa"] = {
        "branch": "qa",
        "domain": "qa.example.com",
        "db_name": "acme_qa",
        "filestore_path": "/var/lib/odoo/filestore/acme_qa",
        "clone_from": "production",
        "sanitize": True,
    }
    config.write_text(yaml.safe_dump(data, sort_keys=False))

    prod = runner.invoke(app, ["--project-dir", str(repo), "env", "destroy", "production", "--yes"])
    assert prod.exit_code != 0
    assert "Refusing to destroy the production" in prod.output

    result = runner.invoke(app, ["--project-dir", str(repo), "env", "destroy", "qa", "--yes"])
    assert result.exit_code == 0, result.output
    assert "qa" not in yaml.safe_load(config.read_text())["environments"]


def test_env_destroy_purge_is_guarded(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    config = _write_config(repo)
    data = yaml.safe_load(config.read_text())
    data["environments"]["qa"] = {
        "branch": "qa",
        "domain": "qa.example.com",
        "db_name": "acme_qa",
        "filestore_path": "/var/lib/odoo/filestore/acme_qa",
        "clone_from": "production",
        "sanitize": True,
    }
    config.write_text(yaml.safe_dump(data, sort_keys=False))

    result = runner.invoke(app, ["--project-dir", str(repo), "env", "destroy", "qa", "--yes", "--purge"])
    assert result.exit_code != 0
    assert "--purge DB/filestore destruction is not implemented yet" in result.output
    assert "qa" in yaml.safe_load(config.read_text())["environments"]
