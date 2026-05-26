from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
import click
from pydantic import BaseModel, Field, field_validator, model_validator


class ProjectConfig(BaseModel):
    name: str = "my-odoo-project"
    odoo_version: str = "19.0"


class RuntimeConfig(BaseModel):
    type: Literal["docker_compose"] = "docker_compose"
    compose_file: str = "docker-compose.yml"
    reverse_proxy: str = "traefik"
    execution_mode: Literal["docker", "host"] = "host"


class EnvironmentConfig(BaseModel):
    stack: str = "default"
    branch: str
    scheme: Literal["http", "https"] = "https"
    domain: str
    port: int | None = None
    db_name: str
    filestore_path: str
    filestore_volume: str | None = None
    db_selector: bool = False
    clone_from: str | None = None
    sanitize: bool = False
    update_modules: list[str] = Field(default_factory=list)


class PostgresConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    user: str = "odoo"
    password_env: str = "ODOO_DB_PASSWORD"
    service: str = "postgres"
    internal_host: str | None = None
    service_user: str | None = None
    service_password_env: str | None = None

    @model_validator(mode="after")
    def fill_container_defaults(self) -> "PostgresConfig":
        if self.internal_host is None:
            self.internal_host = self.service
        if self.service_user is None:
            self.service_user = self.user
        if self.service_password_env is None:
            self.service_password_env = self.password_env
        return self

    def password(self) -> str:
        value = os.getenv(self.password_env)
        if not value:
            raise RuntimeError(f"Missing required environment variable: {self.password_env}")
        return value

    def service_password(self) -> str:
        env_name = self.service_password_env or self.password_env
        value = os.getenv(env_name)
        if not value:
            raise RuntimeError(f"Missing required environment variable: {env_name}")
        return value


class OdooConfig(BaseModel):
    image: str
    config_path: str = "./odoo.conf"
    addons_paths: list[str] = Field(default_factory=list)
    service: str = "odoo"
    db_host: str | None = None
    db_user: str | None = None
    db_password_env: str | None = None
    filestore_container_path: str = "/var/lib/odoo"
    without_demo: str = "True"


class RemoteBackupConfig(BaseModel):
    type: str = "s3"
    bucket: str | None = None
    endpoint_env: str | None = None
    access_key_env: str | None = None
    secret_key_env: str | None = None


class RetentionConfig(BaseModel):
    daily: int = 7
    weekly: int = 4
    monthly: int = 6


class BackupsConfig(BaseModel):
    local_path: str = "./backups"
    remote: RemoteBackupConfig | None = None
    retention: RetentionConfig = Field(default_factory=RetentionConfig)


class SanitizationConfig(BaseModel):
    sql_files: list[str] = Field(default_factory=list)
    disable_mail_servers: bool = True
    disable_fetchmail: bool = True
    disable_crons: bool = True
    rewrite_base_url: bool = True
    disable_payment_providers: bool = True
    disable_queue_jobs: bool = True
    purge_mail_queue: bool = True
    temp_db_suffix: str = "_incoming"


class HealthcheckConfig(BaseModel):
    path: str = "/web/login"
    scheme: Literal["http", "https"] | None = None
    timeout_seconds: int = 5
    retries: int = 12
    interval_seconds: int = 5


class OdooCtlConfig(BaseModel):
    project: ProjectConfig
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    environments: dict[str, EnvironmentConfig]
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)
    odoo: OdooConfig
    backups: BackupsConfig = Field(default_factory=BackupsConfig)
    sanitization: SanitizationConfig = Field(default_factory=SanitizationConfig)
    healthcheck: HealthcheckConfig = Field(default_factory=HealthcheckConfig)

    @field_validator("environments")
    @classmethod
    def must_have_environments(cls, value: dict[str, EnvironmentConfig]) -> dict[str, EnvironmentConfig]:
        if not value:
            raise ValueError("at least one environment is required")
        return value

    @model_validator(mode="after")
    def validate_environment_graph(self) -> "OdooCtlConfig":
        if self.odoo.db_host is None:
            self.odoo.db_host = self.postgres.internal_host
        if self.odoo.db_user is None:
            self.odoo.db_user = self.postgres.user
        if self.odoo.db_password_env is None:
            self.odoo.db_password_env = self.postgres.password_env

        seen_db_names: dict[str, str] = {}
        seen_filestores: dict[str, str] = {}
        seen_domains: dict[str, str] = {}
        seen_branches: dict[str, str] = {}

        for name, env in self.environments.items():
            if name == "production" and env.clone_from:
                raise ValueError(
                    "Environment 'production' cannot be a clone target; "
                    "cloning drops and recreates the target database without a backup"
                )
            if env.clone_from and env.clone_from not in self.environments:
                known = ", ".join(sorted(self.environments))
                raise ValueError(f"Environment '{name}' clone_from '{env.clone_from}' is not defined. Known: {known}")
            if env.clone_from == name:
                raise ValueError(f"Environment '{name}' cannot clone_from itself")

            if env.db_name in seen_db_names:
                first_env = seen_db_names[env.db_name]
                raise ValueError(
                    f"Environments '{first_env}' and '{name}' cannot share db_name '{env.db_name}'; "
                    "clone and rollback operations drop and recreate target databases"
                )
            seen_db_names[env.db_name] = name

            filestore_identity = (
                f"volume:{env.filestore_volume}:{env.filestore_path}"
                if env.filestore_volume
                else f"path:{env.filestore_path}"
            )
            if filestore_identity in seen_filestores:
                first_env = seen_filestores[filestore_identity]
                raise ValueError(
                    f"Environments '{first_env}' and '{name}' cannot share filestore '{filestore_identity}'; "
                    "clone and rollback operations replace target filestores"
                )
            seen_filestores[filestore_identity] = name

            if env.domain in seen_domains:
                first_env = seen_domains[env.domain]
                first = self.environments[first_env]
                shared_multidb_stack = first.stack == env.stack and first.db_selector and env.db_selector
                if not shared_multidb_stack:
                    raise ValueError(
                        f"Environments '{first_env}' and '{name}' cannot share domain '{env.domain}'; "
                        "deploy and rollback healthchecks would target the wrong instance unless both use db_selector in the same stack"
                    )
            seen_domains[env.domain] = name

            if env.branch in seen_branches:
                first_env = seen_branches[env.branch]
                raise ValueError(
                    f"Environments '{first_env}' and '{name}' cannot share branch '{env.branch}'; "
                    "branch-to-environment mapping must be unique for deploy and rollback to target the right instance"
                )
            seen_branches[env.branch] = name
        return self

    def env(self, name: str) -> EnvironmentConfig:
        try:
            return self.environments[name]
        except KeyError as exc:
            known = ", ".join(sorted(self.environments))
            raise KeyError(f"Unknown environment '{name}'. Known: {known}") from exc

    def referenced_env_vars(self) -> list[str]:
        refs = {self.postgres.password_env}
        if self.postgres.service_password_env:
            refs.add(self.postgres.service_password_env)
        if self.odoo.db_password_env:
            refs.add(self.odoo.db_password_env)
        if self.backups.remote:
            remote = self.backups.remote
            for value in (remote.endpoint_env, remote.access_key_env, remote.secret_key_env):
                if value:
                    refs.add(value)
        return sorted(refs)

    def missing_env_vars(self) -> list[str]:
        return [name for name in self.referenced_env_vars() if not os.getenv(name)]


def load_config(path: str | Path = "odooctl.yml") -> OdooCtlConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise click.ClickException(f"Config file not found: {config_path}")
    data = yaml.safe_load(config_path.read_text())
    return OdooCtlConfig.model_validate(data)


def example_config() -> str:
    return """project:
  name: demo-odoo-project
  odoo_version: "19.0"

runtime:
  type: docker_compose
  compose_file: docker-compose.yml
  reverse_proxy: traefik

postgres:
  host: localhost
  port: 5432
  user: odoo
  password_env: ODOO_DB_PASSWORD

backups:
  local_path: backups
  remote:
    type: s3
    bucket: demo-odoo-backups
    endpoint_env: ODOO_S3_ENDPOINT
    access_key_env: ODOO_S3_ACCESS_KEY
    secret_key_env: ODOO_S3_SECRET_KEY

odoo:
  image: registry.example.com/odoo:19.0
  config_path: ./odoo.conf
  service: odoo
  addons_paths:
    - /mnt/extra-addons
    - /opt/odoo/custom-addons

environments:
  production:
    branch: main
    domain: odoo.example.com
    db_name: odoo_prod
    filestore_path: /var/lib/odoo/filestore/odoo_prod
    update_modules:
      - sale
      - stock
  staging:
    branch: staging
    domain: staging.odoo.example.com
    db_name: odoo_staging
    filestore_path: /var/lib/odoo/filestore/odoo_staging
    clone_from: production
    sanitize: true
    update_modules:
      - sale
      - stock
      - custom_module

sanitization:
  sql_files:
    - .sanitize/staging.sql
    - .sanitize/disable_connectors.sql
  disable_mail_servers: true
  disable_fetchmail: true
  disable_crons: true
  rewrite_base_url: true
  disable_payment_providers: true
  disable_queue_jobs: true
  purge_mail_queue: true
  temp_db_suffix: _incoming

healthcheck:
  path: /web/login
  timeout_seconds: 5
  retries: 12
  interval_seconds: 5
"""
