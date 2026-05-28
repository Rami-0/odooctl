from pathlib import Path

from odooctl.adapters.db import DockerPostgresAdapter, HostPostgresAdapter, make_db_adapter
from odooctl.context import ProjectContext
from odooctl.config import load_config


def write_config(tmp_path: Path, *, mode: str = "docker") -> Path:
    path = tmp_path / "odooctl.yml"
    path.write_text(
        f"""project:
  name: demo
  odoo_version: "19.0"
runtime:
  compose_file: docker-compose.yml
  execution_mode: {mode}
postgres:
  user: odoo
  password_env: ODOO_DB_PASSWORD
  service: db
  internal_host: db
  service_user: postgres
  service_password_env: PG_SERVICE_PASSWORD
odoo:
  image: odoo:19.0
  service: odoo
environments:
  production:
    branch: main
    domain: odoo.example.com
    db_name: odoo_prod
    filestore_path: /srv/filestore/prod
"""
    )
    return path


def test_make_db_adapter_selects_docker_when_configured(tmp_path: Path):
    cfg_path = write_config(tmp_path)
    ctx = ProjectContext.from_config_path(cfg_path)

    adapter = make_db_adapter(ctx)

    assert isinstance(adapter, DockerPostgresAdapter)


def test_make_db_adapter_keeps_host_mode(tmp_path: Path):
    cfg_path = write_config(tmp_path, mode="host")
    ctx = ProjectContext.from_config_path(cfg_path)

    adapter = make_db_adapter(ctx)

    assert isinstance(adapter, HostPostgresAdapter)


def test_docker_postgres_dump_uses_binary_capture(monkeypatch, tmp_path: Path):
    cfg_path = write_config(tmp_path)
    ctx = ProjectContext.from_config_path(cfg_path)
    calls = []

    monkeypatch.setenv("PG_SERVICE_PASSWORD", "service-secret")

    def fake_capture(args, *, cwd, env, stdout_path, check=True):
        calls.append((args, cwd, env, stdout_path, check))

    monkeypatch.setattr("odooctl.utils.shell.run_capture_bytes", fake_capture)

    DockerPostgresAdapter(ctx).dump("odoo_prod", tmp_path / "db.dump")

    args, cwd, env, stdout_path, check = calls[0]
    assert args[:9] == ["docker", "compose", "-f", str(ctx.compose_file), "exec", "-T", "-e", "PGPASSWORD", "db"]
    assert args[-5:] == ["-h", "db", "-U", "postgres", "-Fc", "-d", "odoo_prod"][-5:]
    assert "pg_dump" in args
    assert cwd == str(tmp_path)
    assert env == {"PGPASSWORD": "service-secret"}
    assert stdout_path == tmp_path / "db.dump"
    assert check is True


def test_config_defaults_container_and_odoo_fields(tmp_path: Path):
    cfg_path = tmp_path / "odooctl.yml"
    cfg_path.write_text(
        """project:
  name: demo
  odoo_version: "19.0"
postgres:
  service: db
  user: odoo
  password_env: ODOO_DB_PASSWORD
odoo:
  image: odoo:19.0
environments:
  production:
    branch: main
    domain: odoo.example.com
    db_name: odoo_prod
    filestore_path: /srv/filestore/prod
"""
    )

    cfg = load_config(cfg_path)

    assert cfg.runtime.execution_mode == "host"
    assert cfg.postgres.internal_host == "db"
    assert cfg.postgres.service_user == "odoo"
    assert cfg.postgres.service_password_env == "ODOO_DB_PASSWORD"
    assert cfg.odoo.db_host == "db"
    assert cfg.odoo.db_user == "odoo"
    assert cfg.odoo.db_password_env == "ODOO_DB_PASSWORD"
    assert cfg.env("production").scheme == "https"
    assert cfg.env("production").stack == "default"
