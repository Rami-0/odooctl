# odooctl autonomous sprint progress

**Sprint started:** 2026-05-26
**Cadence:** every 39 minutes
**Duration:** 24 hours
**Primary plan:** `docs/plans/2026-05-26-odooctl-vnext-build-plan.md`
**Experiment reference:** `experiments/odoo19-community-staging/README.md`

## Operating rules

- Work through the v-next plan in order: M0 → M1 → M2 → M3 → M4 → M5.
- Prefer significant, verified slices over tiny cosmetic changes.
- Before each run: read this file, inspect git status, inspect the plan, choose the next unfinished task.
- After each run: update this file with what changed, tests run, commit/push status, blockers, and next task.
- Do not mark a task complete unless tests or equivalent verification passed.

## Progress log

### 2026-05-26 — Sprint initialized

- Paused old sprint and replaced its goal with the v-next build plan.
- Created this progress tracker.
- Current next target: M0 — test-harness hygiene.

### 2026-05-26T15:02:31+00:00 — M0 test-harness hygiene

- Completed the first M0 slice: added pytest environment isolation and registered unit/integration/docker markers.
- Files changed: `tests/conftest.py`, `pyproject.toml`.
- Verification:
  - `pytest -q` — 97 passed.
  - `ODOO_DB_PASSWORD=ambient-secret pytest -q` — 97 passed.
  - `pytest -m integration` — 97 deselected / 0 selected, exit 0.
- Commit SHA: d5ea2d9 (`Harden pytest harness environment isolation`).
- Push status: pushed to `origin/master` (`a9747a3..d5ea2d9`); follow-up progress-status commit may be pushed separately.
- Blockers/open questions: none.
- Next recommended task: start M1 with `ProjectContext` and `doctor` tests.

### 2026-05-26T15:45:00+00:00 — M1 ProjectContext + doctor foundation

- Completed the first M1 slice: added `ProjectContext` for config-rooted path resolution, side-effect-free preflight checks, and a new `odooctl doctor` command with human and JSON output.
- Files changed: `odooctl/context.py`, `odooctl/preflight.py`, `odooctl/commands/doctor.py`, `odooctl/main.py`, `tests/test_context.py`, `tests/test_doctor.py`, `docs/plans/progress.md`.
- Verification:
  - `pytest -q tests/test_context.py tests/test_doctor.py tests/test_cli_smoke.py` — 12 passed.
  - `pytest -q` — 101 passed.
- Commit SHA: 5c3dc39 (`Add ProjectContext and doctor preflight`).
- Push status: pushed to `origin/master` (`7e956d3..5c3dc39`).
- Blockers/open questions: none.
- Next recommended task: thread `ProjectContext` through existing commands so compose, metadata, backups, git, sanitization SQL, and config paths stop depending on process cwd.

### 2026-05-26T16:36:14+00:00 — M1 context threading completed

- Completed the remaining M1 slice: threaded `ProjectContext` through deploy, backup, clone, restore, rollback, status, logs, update-modules, and validate command paths.
- Rooted compose execution at the project root, moved metadata reads/writes to `ProjectContext.state_dir`, rooted backup and filestore paths, ran git commands from the project root, and resolved sanitization SQL files relative to the project root.
- Added backward-compatible `postgres.service` default and switched status PostgreSQL service detection to that config field instead of hardcoded `postgres`.
- Files changed: `odooctl/commands/backup.py`, `odooctl/commands/clone.py`, `odooctl/commands/deploy.py`, `odooctl/commands/logs.py`, `odooctl/commands/restore.py`, `odooctl/commands/rollback.py`, `odooctl/commands/status.py`, `odooctl/commands/update_modules.py`, `odooctl/commands/validate.py`, `odooctl/config.py`, `odooctl/odoo/sanitize.py`, `tests/test_clone.py`, `docs/plans/progress.md`.
- Verification:
  - `pytest -q` — 101 passed.
- Commit SHA: 53c6905 (`Thread ProjectContext through commands`).
- Push status: pushed to `origin/master` (`e8f0b73..53c6905`).
- Blockers/open questions: none.
- Next recommended task: start M2 with additive config fields for execution mode and container PostgreSQL/Odoo connection settings.

### 2026-05-26T17:23:37+00:00 — M2 Docker DB adapter foundation

- Completed an M2 foundation slice: added additive execution-mode/container DB/Odoo config fields, binary-safe command helpers, Docker Compose byte stream helpers, and a DB adapter factory with host and Docker PostgreSQL implementations.
- Threaded the DB adapter selection into backup, restore, clone, and deploy preflight while preserving host-mode/backward-compatible test behavior for existing configs.
- Files changed: `odooctl/config.py`, `odooctl/utils/shell.py`, `odooctl/adapters/docker_compose.py`, `odooctl/adapters/db.py`, `odooctl/commands/backup.py`, `odooctl/commands/clone.py`, `odooctl/commands/deploy.py`, `odooctl/commands/restore.py`, `odooctl/odoo/sanitize.py`, `tests/test_db_adapter.py`, `tests/test_shell.py`, `docs/plans/progress.md`.
- Verification:
  - `pytest -q tests/test_db_adapter.py tests/test_shell.py tests/test_config.py` — 22 passed.
  - `pytest -q` — 107 passed.
- Commit SHA: 704a50c (`Add Docker PostgreSQL adapter foundation`); progress follow-up commit 6d7d568 (`Record Docker adapter sprint progress`).
- Push status: pushed to `origin/master` through 6d7d568 (`704a50c..6d7d568` follow-up push).
- Blockers/open questions: `runtime.execution_mode` currently remains backward-compatible default `host`; switching the product default to `docker` needs broader test fixture updates and may be best done with the remaining M2 command wiring.
- Next recommended task: finish M2 command behavior by adding scheme/port/db-selector URL handling, Odoo module-update DB flags, and tests around container-mode backup/restore command arguments.

### 2026-05-26T18:07:52+00:00 — M2 module-update flags and URL handling

- Completed the remaining M2 command-behavior slice: module updates now build official-image-safe Odoo invocations with `-c`, `--db_host`, `--db_user`, and `--db_password` from config/env, and deploy/clone/update-modules pass those settings through.
- Added scheme/port-aware URL construction plus optional `?db=<db_name>` selector support for deploy, clone, restore, rollback, status, and sanitization base-url rewrites; status continues to use `cfg.postgres.service` for PostgreSQL service state.
- Files changed: `odooctl/adapters/reverse_proxy.py`, `odooctl/commands/clone.py`, `odooctl/commands/deploy.py`, `odooctl/commands/restore.py`, `odooctl/commands/rollback.py`, `odooctl/commands/status.py`, `odooctl/commands/update_modules.py`, `odooctl/odoo/healthcheck.py`, `odooctl/odoo/module_update.py`, `odooctl/odoo/sanitize.py`, `tests/test_module_update.py`, `docs/plans/progress.md`.
- Verification:
  - `pytest -q tests/test_module_update.py tests/test_status.py tests/test_healthcheck.py` — 8 passed.
  - `pytest -q` — 109 passed.
  - `ODOO_DB_PASSWORD=ambient-secret pytest -q` — 109 passed.
- Commit SHA: 48c6797 (`Fix Docker module update flags and URLs`).
- Push status: pushed to `origin/master` (`4db57fb..48c6797`); follow-up progress-status commit may be pushed separately.
- Blockers/open questions: no Docker integration run in this tick; real experiment-stack verification remains needed for container backup/restore/update-modules acceptance.
- Next recommended task: start M3 with temp-DB clone/sanitize/swap choreography and `db_selector` multi-db validation tests.

### 2026-05-26T18:50:40+00:00 — M3 temp DB clone/sanitize/swap foundation

- Completed the first M3 safety slice: clone now restores into `<target_db><temp_db_suffix>`, sanitizes the temporary DB before exposure, then terminates target connections, drops the old target DB, and renames the prepared temp DB into place.
- Added guarded DB swap helpers that refuse production targets, plus default `sanitization.temp_db_suffix: _incoming`.
- Expanded default sanitization for real Odoo deployments with guarded OCA `queue_job`, `base_automation`, and unsent `mail_mail` spool cleanup SQL.
- Relaxed same-domain validation for explicit same-stack `db_selector: true` multi-db environments while preserving the old failure for non-selector/shared-domain configs.
- Files changed: `odooctl/commands/clone.py`, `odooctl/config.py`, `odooctl/odoo/db_swap.py`, `odooctl/odoo/sanitize.py`, `examples/odooctl.yml`, `tests/test_clone.py`, `tests/test_clone_swap.py`, `tests/test_sanitize.py`, `docs/plans/progress.md`.
- Verification:
  - `pytest -q tests/test_clone.py tests/test_clone_swap.py tests/test_sanitize.py tests/test_config.py` — 35 passed.
  - `pytest -q` — 112 passed.
- Commit SHA: 0ea2ad2 (`Add safe clone temp database swap`).
- Push status: pushed to `origin/master` (`86f701a..0ea2ad2`).
- Blockers/open questions: Docker experiment-stack verification still not run; filestore named-volume adapter remains outstanding for M3.
- Next recommended task: add explicit config tests for `db_selector` multi-db sharing and then implement Docker volume filestore adapter.

### 2026-05-26T19:39:39+00:00 — M3 multi-db validation and Docker volume filestore

- Completed the remaining unit-level M3 configuration and filestore slice: added explicit tests for same-stack `db_selector` domain sharing, named-volume filestore identity validation, and Docker-volume filestore archive/restore/copy command construction.
- Added `filestore_volume` to environment config and wired backup, restore, and clone to choose a Docker-volume filestore backend when configured, while preserving host-path behavior and existing command monkeypatch compatibility.
- Implemented Docker-volume filestore streaming through `docker compose exec -T` using tar/zstd byte streams, so hosts do not need a bind-mounted Odoo filestore path.
- Files changed: `odooctl/config.py`, `odooctl/adapters/filestore.py`, `odooctl/commands/backup.py`, `odooctl/commands/clone.py`, `odooctl/commands/restore.py`, `tests/test_config.py`, `tests/test_filestore_volume.py`, `docs/plans/progress.md`.
- Verification:
  - `pytest -q tests/test_config.py tests/test_filestore_volume.py` — 20 passed.
  - `pytest -q` — 118 passed.
- Commit SHA: 67b3f32 (`Add Docker volume filestore support`); progress follow-up commits 7096faa and a4d801a.
- Push status: pushed to `origin/master` through a4d801a (`1064537..a4d801a`).
- Blockers/open questions: Docker experiment-stack verification still not run; unit coverage verifies command construction only.
- Next recommended task: run real experiment-stack verification for Docker backup/clone/restore/update-modules, then start M4 project registry if the stack passes.

### 2026-05-26T20:23:00+00:00 — M4 project registry and project selection foundation

- Completed the first M4 product-surface slice: added an XDG-backed global project registry, `odooctl project add/list/use/remove/current`, and global `-p/--project` plus `-C/--project-dir` resolution with the planned precedence for existing commands.
- Registry state now lives under `${XDG_CONFIG_HOME:-~/.config}/odooctl/config.toml`, records active project plus per-project path/config, and resolves registered projects into `ProjectContext` without moving `.odooctl/` state out of the project repo.
- Files changed: `odooctl/registry.py`, `odooctl/commands/project.py`, `odooctl/main.py`, `tests/test_registry.py`, `docs/plans/progress.md`.
- Verification:
  - `pytest -q tests/test_registry.py tests/test_cli_smoke.py` — 12 passed.
  - `pytest -q` — 122 passed.
- Commit SHA: 3d02faa (`Add project registry commands`); progress follow-up commit 8bd01c7.
- Push status: pushed to `origin/master` through 8bd01c7 (`d231673..8bd01c7`).
- Blockers/open questions: real Docker experiment-stack verification remains outstanding; M4 env lifecycle commands are not implemented yet.
- Next recommended task: implement `env list/show/create/destroy` config editing with production destroy guards and mocked clone provisioning tests.

### 2026-05-26T21:05:33+00:00 — M4 env lifecycle foundation

- Completed the M4 env command foundation: added `odooctl env list/show/create/destroy`, wired the env sub-app into the CLI, and added config editing for environment creation/removal.
- `env create` validates the full updated YAML before writing, inherits source stack/filestore volume/update modules where appropriate, supports shared-stack `--db-selector`, and provisions via the existing safe clone path unless `--no-provision` is passed.
- `env destroy` refuses `production`, requires `--yes`, removes non-production config blocks, and deliberately guards `--purge` because DB/filestore purge execution is not yet implemented.
- Files changed: `odooctl/commands/env.py`, `odooctl/main.py`, `tests/test_env_cmd.py`, `docs/plans/progress.md`.
- Verification:
  - `pytest -q tests/test_env_cmd.py tests/test_registry.py` — 9 passed.
  - `pytest -q` — 127 passed.
- Commit SHA: aa9e95b (`Add environment lifecycle commands`).
- Push status: pushed to `origin/master` (`7512ca0..aa9e95b`); follow-up progress-status commit may be pushed separately.
- Blockers/open questions: destructive `env destroy --purge` still needs implementation against the DB and filestore adapter factories, with production guards and tests.
- Next recommended task: implement guarded non-production `env destroy --purge` adapter execution, then run Docker experiment-stack verification for backup/clone/restore/update-modules.

### 2026-05-26T21:52:38+00:00 — M4 guarded env purge

- Completed the M4 purge follow-up: `odooctl env destroy --purge --yes <env>` now refuses production via the existing destroy guard, drops the non-production database through the selected host/Docker DB adapter, deletes the matching host-path or Docker-volume filestore, then removes the environment config only after purge succeeds.
- Added `drop()` to DB adapters using the existing terminate/drop SQL helpers and added `delete()` to host and Docker-volume filestore adapters.
- Files changed: `odooctl/adapters/db.py`, `odooctl/adapters/filestore.py`, `odooctl/commands/env.py`, `tests/test_env_cmd.py`, `docs/plans/progress.md`.
- Verification:
  - `pytest -q tests/test_env_cmd.py tests/test_filestore_volume.py tests/test_clone_swap.py` — 10 passed.
  - `pytest -q` — 127 passed.
- Commit SHA: fc9095b (`Implement guarded environment purge`); progress follow-up commit 5fed41a.
- Push status: pushed to `origin/master` through 5fed41a (`036d4e6..5fed41a`).
- Blockers/open questions: real Docker experiment-stack verification still not run.
- Next recommended task: run Docker experiment-stack verification for backup/clone/restore/update-modules; if not feasible, start M5 PyPI metadata/install docs.

### 2026-05-26T22:34:42+00:00 — M5 PyPI metadata and install docs

- Completed the first M5 distribution slice: added PyPI-facing package metadata, project URLs, classifiers, keywords, author/license declarations, and the optional `s3` extra.
- Updated operator installation docs to make `pipx install odooctl` the primary path, document `uv tool install`, explain Docker vs host PostgreSQL runtime prerequisites, and point users at `project add` + `doctor` after install.
- Files changed: `pyproject.toml`, `README.md`, `docs/installation.md`, `docs/plans/progress.md`.
- Verification:
  - `python -m pytest -q` — 127 passed.
  - `uv pip install build && python -m build --sdist --wheel` — successfully built `odooctl-0.1.0.tar.gz` and `odooctl-0.1.0-py3-none-any.whl`.
- Commit SHA: 6691d63 (`Add package metadata and install docs`).
- Push status: pushed to `origin/master` (`9d4ba02..6691d63`); follow-up progress-status commit may be pushed separately.
- Blockers/open questions: `uv pip install build` updated the local development venv only; no repo file changes from that install. Real Docker experiment-stack verification remains outstanding.
- Next recommended task: add the schedule command for systemd timer / cron generation, then continue M5 redaction precision.

### 2026-05-26T23:16:41+00:00 — M5 schedule generation

- Completed the M5 scheduled-ops slice: added `odooctl schedule` to render installable systemd timer/service pairs or cron entries for `backup` and `doctor` runs.
- The command follows the plan UX (`odooctl schedule backup --env production --cron "0 2 * * *"`) while also supporting cron aliases, explicit users, and custom `odooctl` binary paths; generation is output-only so operators install the files themselves.
- Files changed: `odooctl/commands/schedule.py`, `odooctl/main.py`, `tests/test_schedule.py`, `README.md`, `docs/plans/progress.md`.
- Verification:
  - `pytest -q tests/test_schedule.py tests/test_cli_smoke.py` — 12 passed.
  - `pytest -q` — 131 passed.
- Commit SHA: pending.
- Push status: pending.
- Blockers/open questions: real Docker experiment-stack verification remains outstanding.
- Next recommended task: improve redaction precision with configurable minimum secret length/ignored values, then continue toward real S3 optional adapter.

## Milestone checklist

### M0 — Test-harness hygiene

- [x] Add `tests/conftest.py` with environment isolation.
- [x] Register pytest markers for `unit`, `integration`, `docker`.
- [x] Ensure `pytest -q` passes with `ODOO_DB_PASSWORD` set and unset.

### M1 — ProjectContext + doctor

- [x] Add `odooctl/context.py` and root paths/state at project root.
- [x] Add `odooctl/preflight.py`.
- [x] Add `odooctl doctor` with human and JSON output.
- [x] Thread context through commands.

### M2 — Docker-native execution mode

- [x] Add config fields: `execution_mode`, container DB settings, per-env scheme.
- [x] Add binary-safe command runner.
- [x] Add Docker PostgreSQL adapter.
- [x] Fix module update DB flags.
- [x] Fix status DB service name.

### M3 — Safe clone + multi-db + filestore volumes

- [x] Implement temp DB clone/sanitize/swap.
- [x] Support multi-db mode with `db_selector`.
- [x] Add Docker volume filestore adapter.
- [x] Expand sanitization for queue jobs and mail spool.

### M4 — Global project registry + env lifecycle

- [x] Add project registry.
- [x] Add `project` command group.
- [x] Add `env` command group.
- [x] Support `-p/--project` and `-C/--project-dir` UX.

### M5 — Distribution, scheduling, polish

- [x] Add PyPI metadata and install docs.
- [x] Add schedule command for systemd timer / cron generation.
- [ ] Improve redaction precision.
- [ ] Add real S3 optional adapter.
- [ ] Update operator docs.
