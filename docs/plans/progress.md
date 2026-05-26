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

## Milestone checklist

### M0 — Test-harness hygiene

- [x] Add `tests/conftest.py` with environment isolation.
- [x] Register pytest markers for `unit`, `integration`, `docker`.
- [x] Ensure `pytest -q` passes with `ODOO_DB_PASSWORD` set and unset.

### M1 — ProjectContext + doctor

- [ ] Add `odooctl/context.py` and root paths/state at project root.
- [ ] Add `odooctl/preflight.py`.
- [ ] Add `odooctl doctor` with human and JSON output.
- [ ] Thread context through commands.

### M2 — Docker-native execution mode

- [ ] Add config fields: `execution_mode`, container DB settings, per-env scheme.
- [ ] Add binary-safe command runner.
- [ ] Add Docker PostgreSQL adapter.
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
