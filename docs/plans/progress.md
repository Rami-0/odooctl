# odooctl Control-Plane Progress

Primary plan index: `docs/plans/README.md`

## Operating rules

- Work milestones M6 → M15 in order unless explicitly reprioritized.
- Before each run: inspect git status, read active milestone plan, inspect current code.
- After each run: update this file with changed files, tests, result, blockers, and next step.
- Do not mark a task complete unless verified.
- Engine-touching milestones require real Odoo fixture evidence.

## Progress log

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
**Push status:** failed in Claude Code run because the execution environment lacked remote credentials; retry pending from worker handoff
**Blockers:** none
**Next step:** M7 operation engine — add operation models/store/events/audit/locks, wrap mutating services in run_operation

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

- [ ] Add operation models/store/events/audit/locks.
- [ ] Wrap mutating services in `run_operation`.
- [ ] Add `odooctl ops list/show/logs/cancel`.
- [ ] Add per-environment lock tests.
- [ ] Add audit-chain tests.
- [ ] Verify live backup/clone emits events and audit.

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
