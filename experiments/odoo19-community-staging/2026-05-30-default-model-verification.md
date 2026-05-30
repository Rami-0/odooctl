# Odoo 19 Community staging experiment — 2026-05-30

Date: 2026-05-30
Agent/model: default Hermes integration model in this Telegram session
Repo: `/home/dev/odooctl`
Commit under test: `08d8495`
Experiment fixture: `experiments/odoo19-community-staging`

## Purpose

Re-run the real Odoo Docker integration after M5 completion and record what is working/passing now, using the default model workflow before asking Claude for a separate read-only audit.

## Environment

- Docker server: `29.4.2`
- Docker Compose: `v5.1.3`
- uv: `0.11.16`
- Python: `3.11.15`
- Odoo image/service: `odoo:19.0`
- PostgreSQL image/service: `postgres:17`
- Stack state during run:
  - `odoo19-community-staging-db-1` — up/healthy
  - `odoo19-community-staging-odoo-1` — up, host port `18069 -> 8069`

## Repo gates passed

```bash
uv run pytest -q
# 136 passed

uv run ruff check .
# All checks passed

uv run python -m build
# Successfully built odooctl-0.1.0.tar.gz and odooctl-0.1.0-py3-none-any.whl
```

## Real Docker/Odoo checks passed

Commands were run from `experiments/odoo19-community-staging` with `ODOO_DB_PASSWORD=odoo`.

### Config validation

```bash
uv run python -m odooctl validate --config odooctl.yml
```

Result: passed.

- Config valid for project `odoo19-community-staging-experiment`.
- Environments: `production`, `staging`.
- Referenced environment variables were set.

### Doctor/preflight

```bash
uv run python -m odooctl doctor --config odooctl.yml
```

Result: passed.

- Config loaded.
- Project root exists.
- Compose file exists.
- Environment variables present.
- Sanitization SQL exists.
- Redaction policy warning is expected because the local test password is the common value `odoo`, intentionally ignored by the redaction policy.

### Status JSON

```bash
uv run python -m odooctl status --environment production --config odooctl.yml --json-output
```

Result: passed.

Observed:

- `current_git_commit`: `08d8495`
- production URL: `http://localhost:18069`
- production health URL: `http://localhost:18069/web/login?db=odoo_prod`
- latest previous backup metadata was readable.

### Backup

```bash
uv run python -m odooctl backup production --config odooctl.yml
```

Result: passed.

Created backup:

- `backups/production_2026-05-30_114222`
- `filestore.tar` detected by `file` as `POSIX tar archive (GNU)`
- manifest present with keys including:
  - `artifact_paths`
  - `backup_id`
  - `backup_mode`
  - `checksums`
  - `db_dump`
  - `db_name`
  - `docker_image`
  - `environment`
  - `filestore`
  - `git_commit`
  - `status`
  - `timestamp`

### Restore

```bash
uv run python -m odooctl restore production --backup production_2026-05-30_114222 --config odooctl.yml
```

Result: passed.

- Existing production DB connections were terminated.
- Production was restored from `production_2026-05-30_114222`.

### Clone production → staging with sanitization

```bash
uv run python -m odooctl clone production staging --sanitize --config odooctl.yml
```

Result: passed.

Observed:

- Temporary DB restore/sanitize/swap path ran.
- Optional sanitization SQL blocks handled missing tables safely.
- Staging DB replaced via drop/rename after terminating old connections.
- Filestore copy completed.
- Odoo module update ran during clone.
- Odoo service restarted.
- Staging URL reported: `http://localhost:18069`.

### Update modules

```bash
uv run python -m odooctl update-modules staging --modules base --config odooctl.yml
```

Result: passed.

- Official Odoo image command ran with explicit DB connection settings.
- `base` module update completed and Odoo shut down cleanly after init.

### HTTP login check

```bash
curl -I 'http://localhost:18069/web/login?db=odoo_staging'
```

Result: passed.

- HTTP `302 FOUND` returned.
- This is acceptable for Odoo login routes.

### Database check

```sql
select current_database(), count(*) from ir_module_module;
```

Result from PostgreSQL container:

- `current_database`: `odoo_staging`
- module count: `695`

## What is working now

- Project config validation.
- Doctor/preflight checks.
- JSON status output.
- Docker-native PostgreSQL backup/restore.
- Plain POSIX `filestore.tar` archive format.
- Restore into production from a real backup artifact.
- Safe production-to-staging clone through temp DB restore/sanitize/swap.
- Docker-volume filestore copy.
- Staging sanitization hooks.
- Official Odoo image module updates with explicit DB flags.
- Multi-database local Odoo serving through `?db=` selector.
- Odoo login healthcheck behavior accepting HTTP 302.
- Full Python test suite, lint, and package build.

## Notes / caveats

- This is still a local Odoo 19 Community Docker fixture, not a live customer production server.
- The test password is intentionally `odoo`; doctor warns that it is short/common and ignored by redaction, which is expected for this fixture.
- Integration CI is not yet automated; this verification was manually run against the local Docker stack.
- Open-source release hygiene files still need attention before a polished public release: root `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and `CHANGELOG.md`.
