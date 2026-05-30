# Changelog

All notable changes to `odooctl` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-05-30

Initial public release of `odooctl`, a CLI-first, Odoo-aware deployment
platform for self-hosted Odoo projects using Docker Compose.

This release closes the v-next milestones M0 through M5 and ships the MVP
foundation: Docker-native database and filestore operations, project and
environment management, scheduled operation generation, install metadata,
secret redaction, optional real S3 uploads, documentation, and tests.

### Added

- **M0 — Test-harness hygiene.** Pytest environment isolation and
  registered `unit`, `integration`, and `docker` markers so the default
  suite runs without Docker or live infrastructure.
- **M1 — Project context and `doctor`.** `ProjectContext` resolves all
  paths relative to the configuration root, and a new `odooctl doctor`
  command runs side-effect-free preflight checks with human and JSON
  output. Context is threaded through deploy, backup, clone, restore,
  rollback, status, logs, update-modules, and validate.
- **M2 — Docker execution mode.** Additive `runtime.execution_mode` and
  container PostgreSQL/Odoo configuration fields. New host and Docker
  PostgreSQL adapters, binary-safe command helpers, Docker Compose byte
  stream helpers, and an adapter factory. Module updates build official
  image-safe Odoo invocations with `-c`, `--db_host`, `--db_user`, and
  `--db_password` from config and environment.
- **M3 — Safer clone and Docker filestores.** Clone restores into a
  temporary database, sanitizes it before exposure, then terminates target
  connections, drops the old target, and renames into place. Named-volume
  filestore adapter for Docker, with archive/restore/copy command
  construction and same-stack `db_selector` validation.
- **M4 — Project and environment registry.** XDG-backed global project
  registry with `odooctl project add/list/use/remove/current`, plus global
  `-p/--project` and `-C/--project-dir` resolution. Environment lifecycle
  commands: `odooctl env list/show/create/destroy`, including a guarded
  env purge.
- **M5 — Productization.** PyPI/pipx install metadata, scheduled
  operation generation (`odooctl schedule backup`, `odooctl schedule
  doctor`), precise secret redaction with configurable
  `redaction.min_secret_length` and `redaction.ignore_values`, an optional
  real S3 adapter behind the `s3` extra, expanded documentation under
  `docs/`, runnable examples under `examples/`, and broader test
  coverage.

### Security

- Secrets are referenced via environment variables and `*_env` config
  fields and are never stored in the repository or in checked-in
  configuration.
- Logs redact environment values whose variable names look secret-bearing
  (`PASSWORD`, `SECRET`, `TOKEN`, `KEY`, `PASSWD`); the redaction policy
  is configurable.
- `odooctl doctor` warns when referenced secrets are shorter than the
  configured minimum or fall on the redaction ignore list.

[Unreleased]: https://github.com/Rami-0/odooctl/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Rami-0/odooctl/releases/tag/v0.1.0
