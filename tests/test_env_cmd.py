from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from odooctl.main import app

runner = CliRunner()


def _all_output(result) -> str:
    """Full CLI error surface across click versions.

    click >= 8.2 splits stderr out of ``result.output`` and newer runners keep
    unrendered ``ClickException``s on ``result.exception`` instead of printing
    them, so an error message may live in any of the three places.
    """
    import click

    out = result.output
    try:
        err = result.stderr
    except (ValueError, AttributeError):
        err = ""
    exc_msg = ""
    if isinstance(result.exception, click.ClickException):
        exc_msg = result.exception.format_message()
    return out + (err or "") + exc_msg


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

    from odooctl.services.models import CloneResult

    def fake_clone(ctx, source, target, sanitize=True, **kwargs):
        calls.append((source, target, sanitize, ctx.project.config_path))
        return CloneResult(url="http://localhost:18069")

    monkeypatch.setattr("odooctl.services.clone.run_clone", fake_clone)

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
    monkeypatch.setattr("odooctl.services.clone.run_clone", lambda *a, **k: (_ for _ in ()).throw(AssertionError("unexpected clone")))

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
    assert "Refusing to destroy protected environment 'production'" in _all_output(prod)

    result = runner.invoke(app, ["--project-dir", str(repo), "env", "destroy", "qa", "--yes"])
    assert result.exit_code == 0, result.output
    assert "qa" not in yaml.safe_load(config.read_text())["environments"]


def test_env_destroy_refuses_protected_tier_env_with_non_production_name(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    config = _write_config(repo)
    data = yaml.safe_load(config.read_text())
    data["environments"]["prod-eu"] = {
        "tier": "production",
        "branch": "main-eu",
        "domain": "eu.example.com",
        "db_name": "acme_prod_eu",
        "filestore_path": "/var/lib/odoo/filestore/acme_prod_eu",
    }
    config.write_text(yaml.safe_dump(data, sort_keys=False))

    result = runner.invoke(app, ["--project-dir", str(repo), "env", "destroy", "prod-eu", "--yes"])
    assert result.exit_code != 0
    assert "Refusing to destroy protected environment 'prod-eu'" in _all_output(result)
    assert "prod-eu" in yaml.safe_load(config.read_text())["environments"]


def test_env_create_refuses_replacing_protected_envs(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    config = _write_config(repo)
    data = yaml.safe_load(config.read_text())
    data["environments"]["prod-eu"] = {
        "tier": "production",
        "branch": "main-eu",
        "domain": "eu.example.com",
        "db_name": "acme_prod_eu",
        "filestore_path": "/var/lib/odoo/filestore/acme_prod_eu",
    }
    config.write_text(yaml.safe_dump(data, sort_keys=False))

    by_name = runner.invoke(
        app,
        ["--project-dir", str(repo), "env", "create", "production", "--clone-from", "production"],
    )
    assert by_name.exit_code != 0
    assert "Refusing to create or replace protected environment 'production'" in _all_output(by_name)

    by_tier = runner.invoke(
        app,
        ["--project-dir", str(repo), "env", "create", "prod-eu", "--clone-from", "production"],
    )
    assert by_tier.exit_code != 0
    assert "Refusing to create or replace protected environment 'prod-eu'" in _all_output(by_tier)


def test_env_destroy_purge_drops_db_and_filestore_before_removing_config(tmp_path: Path, monkeypatch):
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
    calls = []

    class FakeDb:
        def drop(self, db_name: str) -> None:
            calls.append(("drop-db", db_name))

    class FakeFilestore:
        def delete(self, filestore_path: str) -> None:
            calls.append(("delete-filestore", filestore_path))

    monkeypatch.setattr("odooctl.commands.env.make_db_adapter", lambda ctx: FakeDb())
    monkeypatch.setattr("odooctl.commands.env.make_filestore_adapter", lambda ctx, env: FakeFilestore())

    result = runner.invoke(app, ["--project-dir", str(repo), "env", "destroy", "qa", "--yes", "--purge"])
    assert result.exit_code == 0, result.output
    assert calls == [("drop-db", "acme_qa"), ("delete-filestore", "/var/lib/odoo/filestore/acme_qa")]
    assert "qa" not in yaml.safe_load(config.read_text())["environments"]


# ─── env open ─────────────────────────────────────────────────────────────────

def test_env_open_refuses_reserved_name_production(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo)

    result = runner.invoke(
        app, ["--project-dir", str(repo), "env", "open", "production", "--from", "main"]
    )
    assert result.exit_code != 0
    assert "reserved" in _all_output(result).lower()


def test_env_open_refuses_reserved_name_staging(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo)

    result = runner.invoke(
        app, ["--project-dir", str(repo), "env", "open", "staging", "--from", "staging"]
    )
    assert result.exit_code != 0
    assert "reserved" in _all_output(result).lower()


def test_env_open_refuses_duplicate_environment(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    config = _write_config(repo)
    data = yaml.safe_load(config.read_text())
    data["environments"]["existing"] = {
        "branch": "existing",
        "domain": "existing.example.com",
        "db_name": "acme_existing",
        "filestore_path": "/var/lib/odoo/filestore/acme_existing",
    }
    config.write_text(yaml.safe_dump(data, sort_keys=False))

    result = runner.invoke(
        app, ["--project-dir", str(repo), "env", "open", "existing", "--from", "feature/existing"]
    )
    assert result.exit_code != 0
    assert "already exists" in _all_output(result).lower()


def test_env_open_no_provision_writes_config_without_clone(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    config = _write_config(repo)
    monkeypatch.setattr(
        "odooctl.services.clone.run_clone",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("clone should not run")),
    )

    result = runner.invoke(
        app,
        [
            "--project-dir", str(repo),
            "env", "open", "feature-x",
            "--from", "feature/x",
            "--no-provision",
        ],
    )
    assert result.exit_code == 0, result.output
    data = yaml.safe_load(config.read_text())
    assert "feature-x" in data["environments"]
    env = data["environments"]["feature-x"]
    assert env["branch"] == "feature/x"
    assert env["tier"] == "development"
    assert env["clone_from"] == "production"


def test_env_open_with_provision_clones_sanitized_from_source(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo)
    clone_calls: list = []

    from odooctl.services.models import CloneResult

    def fake_clone(ctx, source, target, sanitize=True, **kwargs):
        clone_calls.append((source, target, sanitize))
        return CloneResult(url="http://localhost")

    monkeypatch.setattr("odooctl.services.clone.run_clone", fake_clone)

    result = runner.invoke(
        app,
        [
            "--project-dir", str(repo),
            "env", "open", "dev1",
            "--from", "feature/dev1",
        ],
    )
    assert result.exit_code == 0, result.output
    assert clone_calls == [("production", "dev1", True)]
