# M8 — Import / Takeover and Setup Wizard

## Goal

Support two onboarding paths:

1. Newcomer path: create a managed Odoo project from scratch.
2. Existing-user path: import/take over a running Odoo deployment without redeploying it.

## Strategic importance

This is the main differentiator over simple Odoo hosting panels. Existing self-hosted users need a way to adopt Odoo.sh-like management without moving to SaaS or rebuilding production.

## Files to create

- `odooctl/importer/__init__.py`
- `odooctl/importer/models.py`
- `odooctl/importer/detect.py`
- `odooctl/importer/report.py`
- `odooctl/importer/adopt.py`
- `odooctl/commands/import_cmd.py`
- `odooctl/commands/setup.py`
- tests under `tests/test_import_*.py` and `tests/test_setup.py`

## Import detection

Read-only probes should detect:

- compose file path
- Odoo service name
- Postgres service name
- Odoo image/version
- published HTTP port
- DB host/user/password env references
- DB name candidates
- addons paths
- filestore volume/path
- `odoo.conf` settings if mounted
- `dbfilter`
- `proxy_mode`
- `workers`
- longpolling/gevent config
- custom domains when inferable

## Commands

- `odooctl import [PATH] --preview`
- `odooctl import [PATH] --name <project> --yes`
- `odooctl import [PATH] --force`
- `odooctl setup`
- `odooctl setup --yes --stack odoo-19-community`

## Safety rules

- Preview first by default.
- Detection must not run `compose up`, restart containers, drop DBs, or write data.
- Never inline detected secret values into config.
- Use env-var references or secret store references.
- Refuse to overwrite existing `odooctl.yml` unless `--force`.
- After adoption: run validate, doctor, and verified backup unless explicitly skipped.

## Acceptance criteria

- Import preview works on `experiments/odoo19-community-staging` without disruption.
- Adopted config validates.
- Doctor passes.
- Backup after import is verified.
- Odoo remains reachable during and after import.
- Setup wizard can scaffold a greenfield project.
