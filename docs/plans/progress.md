# odooctl Control-Plane Progress

Primary plan index: `docs/plans/README.md`

## Operating rules

- Work milestones M6 → M15 in order unless explicitly reprioritized.
- Before each run: inspect git status, read active milestone plan, inspect current code.
- After each run: update this file with changed files, tests, result, blockers, and next step.
- Do not mark a task complete unless verified.
- Engine-touching milestones require real Odoo fixture evidence.

## Progress log

### 2026-05-30 17:37 UTC — M8 import/takeover + setup wizard implemented

**Changed files:**
- `odooctl/importer/__init__.py`, `models.py`, `detect.py`, `report.py`, `adopt.py` — added the read-only Docker Compose/Odoo detector, import preview report, generated config builder, and explicit adoption writer with overwrite protection and secret-reference handling.
- `odooctl/commands/import_cmd.py` — added preview-first `odooctl import`; adoption writes config only after `--yes`, registers the project, validates the config, runs doctor unless `--skip-doctor`, and attempts a production safety backup unless `--skip-backup`.
- `odooctl/commands/setup.py` — added `odooctl setup` newcomer scaffolding for greenfield Odoo Compose projects.
- `odooctl/main.py` — registered `import` and `setup` commands and documented the import safety contract in CLI help/docstrings.
- `tests/test_import_detect.py`, `tests/test_import_report.py`, `tests/test_import_adopt.py`, `tests/test_setup.py` — added 51 tests covering detector safety, fixture preview, secret redaction, config generation, adoption/registry/post-adoption checks, and setup scaffolding.
- `docs/plans/progress.md` — recorded M8 verification and handoff.

**Tests:** `uv run pytest tests/test_import_detect.py tests/test_import_report.py tests/test_import_adopt.py tests/test_setup.py -q` — 51 passed; `uv run pytest -q` — 261 passed; `uv run ruff check .` — all checks passed; `uv run python -m build` — sdist and wheel built successfully; smoke checks: `uv run odooctl import experiments/odoo19-community-staging --preview` rendered a 49-line read-only preview, `uv run odooctl setup --yes --stack odoo-19-community --name smoke-odoo --output <tmp>/odooctl.yml` generated config, `uv run odooctl validate --config <tmp>/odooctl.yml` passed schema validation with the expected missing `ODOO_DB_PASSWORD` warning, and fixture adoption with `--skip-doctor --skip-backup` wrote config plus registry entry without touching Docker/DB.
**Result:** M8 implementation is ready for review: import detection is preview-first and file-read-only, adoption is explicit and registers/validates/checks/backs up by default, generated config references secrets by env var name only, and setup scaffolds a greenfield project.
**Implementation commit SHA:** `282d18a`
**Push status:** succeeded — pushed implementation commit `282d18a` and progress commit `3802a85` to `origin/master` using `HOME=/home/dev gh auth setup-git` credentials.
**Blockers:** none
**Next step:** M8 review gate (`t_242010a5`).

### 2026-05-30 17:15 UTC — M7 review gate approved

**Changed files:**
- `docs/plans/progress.md` — recorded the M7 review-gate approval, verification checks, push hygiene, and next milestone.

**Review scope:** `76c555f..903766b` (M7 operation engine, post-review fixes, live fixture evidence, and verification docs)
**Tests:** Claude Code read-only review — approved; `uv run pytest -q` — 210 passed; `uv run ruff check .` — all checks passed; `uv run python -m build` — sdist and wheel built successfully; local audit check against `experiments/odoo19-community-staging/.odooctl/audit.jsonl` — 5 entries, `verify_chain=True`; git hygiene check — `HEAD` matched `origin/master` before this progress entry.
**Result:** M7 review gate approved — operation durability, event timelines, audit chain/tamper detection, lock behavior, mutating-command wrapping, tests, live fixture evidence, and push hygiene are sufficient for milestone closeout.
**Reviewed commit SHA:** `903766b`
**Push status:** succeeded — pushed review-gate progress commit `1069138` to `origin/master` using authenticated GitHub CLI credentials from `/home/dev`; M7 implementation/docs were already synced to `origin/master` at `903766b` before the review entry.
**Blockers:** none
**Next step:** start M8 import/takeover + setup wizard (`t_c6eb31b9`).
**Non-blocking hardening notes for a later milestone:** consider atomic temp-file writes for `OperationStore.save()`, documenting audit-chain truncation limits, improving stale-lock PID-reuse handling, auditing `ops cancel`, and adding a regression test for rollback→restore reentrant lock nesting.

### 2026-05-30 17:07 UTC — M7 live fixture verification passed

**Changed files:**
- `experiments/odoo19-community-staging/2026-05-30-m7-live-fixture-verification.md` — recorded the real Odoo 19 Docker verification for M7 on current `HEAD` `280fea7`, including successful backup/restore/clone/update-modules runs plus operation/event/audit evidence.
- `experiments/odoo19-community-staging/README.md` — added the new M7 verification artifact to the fixture index.
- `docs/plans/progress.md` — marked the live M7 verification blocker resolved and recorded the exact checks run.

**Tests:** `uv run pytest -q` — 210 passed; `uv run ruff check .` — all checks passed; `uv run python -m build` — sdist and wheel built successfully; live fixture checks passed: `validate`, `doctor`, `status --json-output`, `backup production`, `restore production`, `clone production staging --sanitize`, `update-modules staging --modules base`, HTTP login probe, PostgreSQL module-count query, and local `verify_chain=True` against `.odooctl/audit.jsonl`
**Result:** M7 live Odoo 19 fixture verification passed — real backup/restore/clone/update-modules runs emitted operation events, appended audit entries, and preserved a valid audit hash chain.
**Implementation commit SHA:** `b751c85`
**Push status:** succeeded — pushed `b751c85` to `origin/master` via authenticated GitHub CLI HTTPS
**Blockers:** none for M7 live-fixture evidence
**Next step:** complete `t_32688f1c`, let `t_cabeb728` (M7 review gate) promote, then continue to M8.

### 2026-05-30 17:00 UTC — Hourly Kanban manager check

- Active task(s): none running; board is stalled on `t_32688f1c` — **M7 operation engine** assigned to `odoo-backend`, status `blocked`.
- Done since last run: no additional Kanban tasks completed after the M7 review-nit fixes landed locally.
- Board status: `done=2`, `blocked=1`, `ready=0`, `running=0`, `todo=17`; dispatcher pass promoted/spawned nothing.
- Current repo state: branch `master`; `HEAD` `68eb974` (`fix(audit,engine): M7 review nits — prev_hash tamper detection + lock-failure audit trail`); local branch remains **ahead of `origin/master` by 5 commits** while remote `master` is still `76c555f`.
- Tests/result: no new repo tests run by the manager this tick; relying on the blocked worker handoff already recorded for M7 (`uv run pytest -q` → 210 passed, `uv run ruff check .` → all checks passed, `uv run python -m build` → built successfully).
- Push status: GitHub CLI auth is healthy (`gh auth status` OK for `Rami-0`), but the worker never pushed the five local M7 commits; current blocker is operational follow-through, not missing GitHub auth.
- Exact blocker: `t_32688f1c` is blocked as `review-required` after implementation. The handoff says M7 code/tests/review are done locally, but **live Odoo backup/clone fixture verification is still pending** and the branch still needs an authenticated push. Until that task is unblocked/completed, child review gate `t_cabeb728` stays `todo` and M8 cannot promote.
- Next step: unblock or reassign `t_32688f1c` for final M7 closeout — perform the real Odoo 19 fixture verification, push the five local M7 commits, then let `t_cabeb728` (M7 review gate, `odoo-reviewer`) promote.

### 2026-05-30 — M7 review nits resolved (post-review TDD fixes)

**Changed files:**
- `odooctl/operations/audit.py` — `verify_chain` now also checks stored `prev_hash` equals the independently tracked chain position; previously only content+hash mismatch was caught, `prev_hash` field tampering was silently ignored
- `odooctl/operations/engine.py` — `run_operation` now emits an `error`/`end` event and appends a failed audit entry when lock acquisition fails (previously the `LockAcquisitionError` path left no event or audit trail)
- `tests/test_operations.py` — 2 new tests: `test_audit_tamper_detection_modifies_stored_prev_hash` (RED→GREEN via `verify_chain` fix) and `test_engine_lock_acquisition_failure_leaves_audit_trail` (RED→GREEN via engine fix)
- `docs/plans/progress.md` — corrected M7 test count from stale 207/48 to current 210/51 new; documented audit atomicity fix and review-nit fixes

**Tests:** `uv run pytest -q` — 210 passed (51 new); `uv run ruff check .` — all checks passed; `uv run python -m build` — sdist and wheel built successfully
**Result:** M7 review nits resolved — all three post-review fixes applied with strict TDD (failing test first, then implementation)

### 2026-05-30 — M7 operation engine complete

**Changed files:**
- `odooctl/operations/__init__.py` — new package
- `odooctl/operations/models.py` — Operation, Event, AuditEntry, OperationKind, OperationStatus
- `odooctl/operations/store.py` — OperationStore (operation.json + events.jsonl per op)
- `odooctl/operations/locks.py` — EnvironmentLock (O_EXCL atomic, stale-PID clearing, same-thread reentrant)
- `odooctl/operations/audit.py` — AuditStore with SHA-256 hash chain + verify_chain()
- `odooctl/operations/engine.py` — run_operation() context manager
- `odooctl/commands/ops.py` — ops list/show/logs/logs --follow/cancel CLI
- `odooctl/commands/backup.py` — wrapped execute() with run_operation
- `odooctl/commands/restore.py` — wrapped execute() with run_operation
- `odooctl/commands/clone.py` — wrapped execute() (skips for preview)
- `odooctl/commands/deploy.py` — wrapped execute() with run_operation
- `odooctl/commands/rollback.py` — wrapped execute() with run_operation; reentrant lock for inner restore
- `odooctl/commands/update_modules.py` — wrapped execute() with run_operation
- `odooctl/commands/env.py` — wrapped create (provision) and destroy (purge) with run_operation
- `odooctl/main.py` — added ops sub-app
- `tests/test_operations.py` — 37 new tests (TDD; RED first, then GREEN)
- `tests/test_ops_cmd.py` — 11 new CLI tests

**Tests:** `uv run pytest -q` — 208 passed (49 new, including `test_audit_append_concurrent_preserves_chain_integrity` for the atomicity fix); `uv run ruff check .` — all checks passed; `uv run python -m build` — sdist and wheel built successfully
**Result:** M7 operation engine complete — every mutating command records an operation, emits events, appends audit chain, uses per-environment lock
**Implementation commit SHA:** 4e5c483; atomicity fix SHA: 08d89cb
**Push status:** failed — `git push origin HEAD` returned `fatal: could not read Username for 'https://github.com': No such device or address`
**Blockers (post-review fixes — resolved in the entry above):**
- `AuditStore.append()` was non-atomic under concurrent access; fixed with `fcntl.flock` exclusive lock on a sidecar `.lock` file. New test `test_audit_append_concurrent_preserves_chain_integrity` reproduces and verifies the fix.
- `verify_chain` did not detect stored `prev_hash` field tampering — fixed.
- `run_operation` left no event or audit trail on lock acquisition failure — fixed.
- "Verify live backup/clone emits events and audit" was incorrectly marked done; only unit/fake coverage exists. Unchecked in checklist as a required follow-up before M7 can be considered fully DONE.
**Next step:** M8 import/takeover + setup wizard (after live Odoo 19 fixture run for M7 sign-off)

### 2026-05-30 14:57 UTC — M6 review gate approved

**Changed files:**
- `docs/plans/progress.md` — recorded M6 review gate result.

**Review scope:** `d13a91a..76c555f` (M6 service-layer implementation plus progress commits)
**Tests:** `uv run pytest -q` — 159 passed; `uv run ruff check .` — all checks passed; `uv run python -m build` — sdist and wheel built successfully
**Result:** M6 review approved — commands remain thin wrappers, service modules own business logic, CLI behavior/backward compatibility preserved, and new service tests cover success/error paths.
**Reviewed commit SHA:** 76c555f
**Push status:** failed from reviewer workspace: `git push origin HEAD` could not read HTTPS username and `gh auth status` reported no logged-in GitHub hosts.
**Blockers:** none
**Next step:** M7 operation engine (`t_32688f1c`) may proceed.

**Non-blocking follow-ups for M7:**
- Decide whether `ServiceResult[T]` becomes the operation/API envelope or should be removed to avoid a misleading unused API.
- Wire or test `list_environments()`/`ProjectSummary`, or remove the unused seam before it rots.

### 2026-05-30 — M6 service layer complete

**Changed files:**
- `odooctl/services/__init__.py` — new package init
- `odooctl/services/models.py` — ServiceResult, BackupResult, RestoreResult, CloneResult, DeployResult, DoctorReport, StatusReport, EnvironmentSummary, ProjectSummary
- `odooctl/services/context.py` — ServiceContext wrapping ProjectContext
- `odooctl/services/project.py` — get_status() returning StatusReport
- `odooctl/services/environment.py` — list_environments() read-only query
- `odooctl/services/backup.py` — run_backup(), git_commit(), prune_backups(), redact_config_snapshot()
- `odooctl/services/restore.py` — run_restore(), sha256_file(), resolve_backup_dir(), validate_backup_dir()
- `odooctl/services/clone.py` — run_clone() with sanitization and healthcheck
- `odooctl/services/deploy.py` — run_deploy() with preflight, backup, rollout, verify
- `odooctl/commands/backup.py` — thin wrapper; re-exports service utilities for backward compat
- `odooctl/commands/restore.py` — thin wrapper; re-exports sha256_file etc.
- `odooctl/commands/clone.py` — thin wrapper calling run_clone()
- `odooctl/commands/status.py` — thin wrapper rendering StatusReport
- `odooctl/commands/doctor.py` — thin wrapper rendering DoctorReport
- `odooctl/commands/deploy.py` — thin wrapper calling run_deploy()
- `odooctl/commands/env.py` — updated provision to use run_clone() service
- `odooctl/commands/rollback.py` — updated imports from services
- `tests/test_services.py` — 23 new service tests (TDD; written first, ran RED, then GREEN)
- `tests/test_status.py` — updated patches to project service module
- `tests/test_deploy.py` — updated patches to deploy service module
- `tests/test_clone.py` — updated patches to clone service module
- `tests/test_restore.py` — updated patches to restore service module
- `tests/test_env_cmd.py` — updated provision mock to use run_clone service

**Tests:** `uv run pytest -q` — 159 passed; `uv run ruff check .` — all checks passed; `uv run python -m build` — built sdist and wheel successfully
**Result:** M6 service layer complete — commands are thin wrappers, services hold all business logic
**Implementation commit SHA:** 919025b
**Push status:** succeeded on manager retry via authenticated `gh`/HTTPS; pushed `a2438ff` to `origin/master`
**Blockers:** none
**Next step:** M6 review gate (`t_26a59c73`) before M7 operation engine

### 2026-05-30 14:53 UTC — Hourly Kanban manager check

- Active task: `t_26a59c73` — M6 review gate assigned to `odoo-reviewer`; status `running` after dispatcher spawned the reviewer.
- Done since last run: `t_abe7f5bf` — M6 service layer marked `done` after manager verified the implementation handoff, resolved the push blocker, and pushed `a2438ff` to `origin/master`.
- Board status: `done=1`, `running=1`, `todo=18`, `ready=0`, `blocked=0`.
- Tests/result: M6 worker verification already recorded `uv run pytest -q` → 159 passed, `uv run ruff check .` → all checks passed, `uv run python -m build` → sdist/wheel built successfully; manager did not rerun full tests this tick because only board/progress state changed.
- Commit SHA: `a2438ff` (`docs: update M6 verification handoff`) is now synced to `origin/master` before this progress update.
- Push status: succeeded via `gh auth status`, `gh auth setup-git`, and `git push origin HEAD`.
- Blocker: none currently marked blocked on the board.
- Next step: let `odoo-reviewer` complete or block the M6 review gate; only then should M7 operation engine (`t_32688f1c`) promote.

### 2026-05-30 14:02 UTC — Workers rerouted through Claude Code CLI

- Updated all specialist Hermes profiles (`odoo-backend`, `odoo-docker`, `odoo-docs`, `odoo-frontend`, `odoo-planner`, `odoo-reviewer`, `odoo-security`) so Hermes no longer uses the Anthropic API for worker control-plane execution.
- Profile controller routing now uses the working `openai-codex` / `gpt-5.5` Hermes provider; each worker `SOUL.md` explicitly instructs substantive task work to be delegated to the installed `claude` CLI using the `claude-code` workflow.
- Claude Code CLI verification: `claude --version` returned `2.1.158`; `claude auth status --text` reported Claude Max account auth; a repo-local `claude -p` smoke test returned `CLAUDE_CLI_OK`.
- Worker verification: all seven profiles have the `claude-code` skill available and `hermes -p odoo-backend chat -q ...` returned `ODOO_BACKEND_PROFILE_OK`.
- Follow-up auth fix at 14:05 UTC: the worker subprocess uses a profile-scoped `$HOME`, so Claude Code initially saw `Not logged in`; each Odoo profile home now symlinks `.claude` and `.claude.json` to the authenticated `/home/dev` Claude Code account. Profile-home smoke test returned `PROFILE_HOME_CLAUDE_OK`.
- Next step: unblock `t_abe7f5bf` again and let the board dispatch M6 using Claude Code CLI-backed workers.

### 2026-05-30 13:51 UTC — Hourly Kanban manager check

- Active task: `t_abe7f5bf` — M6 service layer assigned to `odoo-backend`; status `running` (run #3 active).
- Board status: `running=1`, `todo=19`, `ready=0`, `blocked=0`, `done=0`.
- Worker diagnostics: the first two `odoo-backend` attempts crashed before tool work because Anthropic returned `HTTP 404: model: claude-sonnet-4`; dispatcher spawned run #3 after promotion/retry.
- Tests/result: no repo milestone tests were run by this manager tick; no code changes verified yet.
- Commit SHA: no milestone commit yet; repo HEAD remains `92e17e6` (`docs: initialize kanban sprint progress`).
- Push status: branch `master` is tracking `origin/master` with no ahead/behind shown before this progress update.
- Blocker: none currently marked blocked on the board; model-name 404 is a worker crash diagnostic to monitor.
- Next step: let `odoo-backend` finish or block M6; then verify `t_26a59c73` M6 review gate promotes to ready for `odoo-reviewer`.

### 2026-05-30 13:56 UTC — Kanban worker crash contained

- Root cause found from `hermes kanban --board odooctl log t_abe7f5bf`:
  - Initial crashes: invalid Anthropic short model id `claude-sonnet-4` returned HTTP 404.
  - Corrected profile models to dated Anthropic ids: `claude-sonnet-4-20250514` and `claude-opus-4-20250514`.
  - Follow-up blocker: Anthropic API returned HTTP 400 extra-usage/quota message: “Third-party apps now draw from your extra usage, not your plan limits. Add more at claude.ai/settings/usage and keep going.”
- Reclaimed the active failing worker and manually blocked `t_abe7f5bf` to prevent retry loops and token/usage waste.
- Board state after containment: no active diagnostics; `t_abe7f5bf` blocked; remaining 19 tasks dependency-gated in todo.
- Next step: add Anthropic extra usage/credits or approve switching worker profiles to a fallback provider/model, then unblock `t_abe7f5bf`.

### 2026-05-30 13:49 UTC — Kanban sprint initialized

- Created Kanban board `odooctl` for M6–M15 control-plane work.
- Queued 20 linked tasks, moving plan-by-plan from M6 through M15 with review/security gates.
- Active task: `t_abe7f5bf` — M6 service layer assigned to `odoo-backend`.
- Model routing verified:
  - Opus: `odoo-planner`, `odoo-reviewer`, `odoo-security`.
  - Sonnet: `odoo-backend`, `odoo-docker`, `odoo-docs`, `odoo-frontend`.
- Created hourly cron manager `c361eaeae4e5` (`odooctl-kanban-hourly-manager`) to inspect board state, dispatch workers, update this progress file, commit management changes, attempt push, and report back to Rami every run.
- Dispatch status: one running task, 19 dependency-gated todo tasks.
- Next step: `odoo-backend` completes M6 service layer, then `odoo-reviewer` reviews M6.

### 2026-05-30 — V1 scope hardened

- Locked v1 deployment mode: single-host Docker Compose only.
- Locked v1 reverse proxy: Traefik adapter behind explicit reverse proxy abstraction.
- Locked v1 UI: FastAPI API + static SPA served by `odooctl serve`.
- Locked import safety contract: read-only detection, no restart/redeploy/DB writes/volume changes/secret printing, preview-first, backup-after-adoption.

### 2026-05-30 — Plan reset

- Cleared old M0–M5 implementation plan pack from `docs/plans/`.
- Created new control-plane plan pack based on repo state, Odoo 19 experiment, `community-sh` UX research, and Claude Opus planning review.
- Next milestone: M6 service layer.

## Milestone checklist

### M6 — Service layer ✓ DONE

- [x] Create `odooctl/services/` package.
- [x] Add structured result models.
- [x] Extract project/status/doctor services.
- [x] Extract backup/restore/clone/deploy services.
- [x] Convert CLI commands into thin wrappers.
- [x] Add service tests (23 new, TDD).
- [x] Verify existing CLI output remains compatible (159 tests pass).
- [x] Run full tests/ruff/build.

### M7 — Operation engine

- [x] Add operation models/store/events/audit/locks.
- [x] Wrap mutating services in `run_operation`.
- [x] Add `odooctl ops list/show/logs/cancel`.
- [x] Add per-environment lock tests.
- [x] Add audit-chain tests (including concurrent-append atomicity fix).
- [x] Verify live backup/clone emits events and audit — passed on the real Odoo 19 fixture; see `experiments/odoo19-community-staging/2026-05-30-m7-live-fixture-verification.md`.

### M8 — Import/takeover + setup wizard

- [ ] Add compose/Odoo detector.
- [ ] Add import preview report.
- [ ] Generate config without redeploy.
- [ ] Register imported project.
- [ ] Run doctor and verified backup after import.
- [ ] Add newcomer `odooctl setup` wizard.
- [ ] Verify import against Odoo 19 fixture.
- [ ] Add tests enforcing import detection has no mutating command calls.
- [ ] Document the import safety contract in CLI help and docs.

### M9 — Environment/branch model

- [ ] Add environment tiers and protected production semantics.
- [ ] Add branch status/drift detection.
- [ ] Add promote staging → production flow.
- [ ] Add ephemeral branch/dev environment flow.
- [ ] Add rollback-on-failed-promote tests.

### M10 — Onboarding catalog

- [ ] Add catalog manifest schema.
- [ ] Add bundled Odoo stack templates.
- [ ] Add OCA/private/Enterprise addon source model.
- [ ] Add companion service templates.
- [ ] Wire catalog into setup wizard.

### M11 — Security architecture

- [ ] Add org/user/role/principal models.
- [ ] Add RBAC action matrix.
- [ ] Add secret store and rotation commands.
- [ ] Add capability tokens.
- [ ] Enforce web/API vs runner privilege split.
- [ ] Expand security docs.

### M12 — API and runner

- [ ] Add optional FastAPI service.
- [ ] Serve static SPA assets from `odooctl serve`.
- [ ] Add durable queue handoff.
- [ ] Add privileged runner.
- [ ] Add operation event streaming.
- [ ] Add API auth/RBAC tests.
- [ ] Verify API-driven backup/clone via runner.

### M13 — Web UI MVP

- [ ] Add web asset/app structure.
- [ ] Projects page.
- [ ] Environment detail page.
- [ ] Doctor/status/backups/operations views.
- [ ] Clone/promote operation buttons.
- [ ] Streaming operation logs.
- [ ] Verify UI only talks to API.

### M14 — Domain/SSL and backup UX

- [ ] Add domain attach/verify/detach service.
- [ ] Add `ReverseProxyAdapter` abstraction.
- [ ] Add Traefik adapter as the only v1 implementation.
- [ ] Add Traefik ACME/DNS-01 support path.
- [ ] Add restore-point browser service.
- [ ] Add restore-to-staging flow.
- [ ] Add DR drill operation.
- [ ] Add encrypted off-site backup option.

### M15 — Migration assistant

- [ ] Add migration matrix.
- [ ] Add module readiness scan.
- [ ] Add upgrade rehearsal operation.
- [ ] Add OpenUpgrade hook support.
- [ ] Add migration report output/API/UI.
