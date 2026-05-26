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
- [ ] Fix module update DB flags.
- [ ] Fix status DB service name.

### M3 — Safe clone + multi-db + filestore volumes

- [ ] Implement temp DB clone/sanitize/swap.
- [ ] Support multi-db mode with `db_selector`.
- [ ] Add Docker volume filestore adapter.
- [ ] Expand sanitization for queue jobs and mail spool.

### M4 — Global project registry + env lifecycle

- [ ] Add project registry.
- [ ] Add `project` command group.
- [ ] Add `env` command group.
- [ ] Support `-p/--project` and `-C/--project-dir` UX.

### M5 — Distribution, scheduling, polish

- [ ] Add PyPI metadata and install docs.
- [ ] Add schedule command for systemd timer / cron generation.
- [ ] Improve redaction precision.
- [ ] Add real S3 optional adapter.
- [ ] Update operator docs.
