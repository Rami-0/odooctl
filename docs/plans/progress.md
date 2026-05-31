# odooctl Control-Plane Progress

Primary plan index: `docs/plans/README.md`

## Operating rules

- Work milestones M6 → M15 in order unless explicitly reprioritized.
- Before each run: inspect git status, read active milestone plan, inspect current code.
- After each run: update this file with changed files, tests, result, blockers, and next step.
- Do not mark a task complete unless verified.
- Engine-touching milestones require real Odoo fixture evidence.

## Progress log

### 2026-05-31 04:08 UTC — M13 review gate approved

**Changed files:**
- `docs/plans/progress.md` — recorded the M13 review-gate approval, verification evidence, non-blocking notes, and next milestone.

**Review scope:** `c370d0c..d937c9d` plus synced manager progress commit `5c74a0f` (M13 static SPA, API serving boundary, packaging, tests/docs, and push hygiene).
**Tests:** Claude Code Opus read-only review — approved with no blocking findings; `uv run pytest tests/test_web.py tests/test_api.py::test_api_does_not_import_privileged -q` — 38 passed, 1 StarletteDeprecationWarning; `uv run pytest tests/test_web.py tests/test_api.py tests/test_security.py -q` — 180 passed, 1 StarletteDeprecationWarning; `uv run ruff check .` — all checks passed; `uv run python -m build` — sdist and wheel built successfully; wheel/sdist manifest smoke verified `odooctl/web/dist/index.html`, `app.js`, `style.css`, and `odooctl/web/README.md` are packaged; `uv run pytest -q` — 575 passed, 1 StarletteDeprecationWarning.
**Result:** Approved — `odooctl serve` serves the packaged static SPA after API routes; the UI talks only to API endpoints, uses typed confirmations for destructive flows, applies RBAC only as display gating while server RBAC remains authoritative, streams operation logs with authenticated fetch/SSE, and ships with focused tests, docs, build packaging, and a clean synced repo.
**Reviewed commit SHA:** `d937c9d`
**Review progress commit SHA:** pending — this entry will be committed after review verification.
**Push status:** pending — will push the review progress update after commit.
**Blockers:** none.
**Non-blocking follow-ups for later:** clamp `max_polls` on `GET /operations/{id}/events`; cache `index.html` instead of synchronous `read_text()` per fallback request; add project/org scoping before any multi-tenant operation reads/cancels; decide later whether typoed API-like paths should 404 instead of returning SPA HTML.
**Next step:** M14 domain/SSL and backup UX (`t_e777c704`) may proceed after this review progress entry is committed and pushed.

### 2026-05-31 04:04 UTC — Hourly Kanban manager check

- Active task(s): `t_cddc7524` — **M13 review gate** assigned to `odoo-reviewer`; status `running` after this manager pass closed the blocked M13 implementation handoff and dispatched the child review gate.
- Done since last run: `t_bf02e8bf` — **M13 web UI MVP** is now manager-approved/closed. The blocker was manager-resolvable because the frontend worker had already committed and pushed the milestone, included explicit verification evidence, and left no unresolved product/policy questions; the only failure was iteration-budget exhaustion while trying to summarize.
- Board status: `done=15`, `running=1`, `blocked=0`, `ready=0`, `todo=4` after dispatch. Milestone order remains intact: M13 review gate is the only active card before M14 `t_e777c704` can promote.
- Current repo state: branch `master`; `HEAD` `d937c9d` (`docs: record M13 push status`); `origin/master` matches local `HEAD` (`ahead/behind = 0/0`); worktree clean before this progress update.
- Tests/result: manager reran `uv run pytest tests/test_web.py tests/test_api.py::test_api_does_not_import_privileged -q` — 38 passed, 1 StarletteDeprecationWarning; `uv run pytest tests/test_web.py tests/test_api.py tests/test_security.py -q` — 180 passed, 1 StarletteDeprecationWarning; `uv run ruff check .` — passed; `uv run python -m build` — succeeded.
- Push status: no new milestone-code push existed before this manager progress update; repo was already synced to `origin/master` at `d937c9d`.
- Blockers: none on the board. Rami input is not required because the blocked card already had durable repo evidence, synced remote state, and a clear next dependency.
- Auto-resolved this run: completed `t_bf02e8bf` with a manager approval summary/metadata, ran `hermes kanban --board odooctl dispatch`, and verified child `t_cddc7524` promoted/spawned. This was safe because the block was procedural and the implementation was independently re-verified against live repo state.
- Next step: let `odoo-reviewer` finish `t_cddc7524`; if it approves M13, verify M14 domain/SSL and backup UX `t_e777c704` promotes/spawns next.

### 2026-05-31 — M13 Web UI MVP implemented

**Changed files:**
- `pyproject.toml` — force-includes `odooctl/web/dist/` in both wheel and sdist builds so packaged installs serve the SPA assets.
- `odooctl/api/app.py` — serves static SPA assets with a catch-all route registered after API routes, falls back to `index.html` for client-side routes, and uses `Path.relative_to()` to prevent static path traversal/sibling-directory leakage.
- `odooctl/commands/serve.py` — auto-detects bundled `odooctl/web/dist/` when `--static-dir` is omitted while preserving explicit `--static-dir` overrides.
- `odooctl/web/__init__.py` — package marker for runner-contract scanning with no privileged imports.
- `odooctl/web/README.md` — developer notes for the no-build static SPA, API-only architecture, routes, RBAC display gating, confirmations, SSE streaming, and runner contract.
- `odooctl/web/dist/index.html` — packaged SPA shell served by `odooctl serve`.
- `odooctl/web/dist/app.js` — vanilla JS dashboard: token handling, projects page, project/environment detail, Overview/Doctor/Operations/Backups/Clone/Promote tabs, RBAC hide/disable logic, typed confirmations, operation enqueue, and SSE log streaming through `/operations/{id}/events`.
- `odooctl/web/dist/style.css` — dashboard styling for cards, tabs, forms, badges, logs, and responsive layouts.
- `docs/web-ui.md` — M13 UI documentation covering serving model, file layout, run commands, hash routes, RBAC display gating, destructive-action confirmation keywords, SSE streaming, and runner-contract checks.
- `tests/test_web.py` — 38 tests covering packaged asset presence/content, pyproject build inclusion, API-only/privilege-split constraints, Doctor/Clone/Promote/backup/SSE affordances, FastAPI static serving and API priority, traversal guard behavior, serve-command auto-detection, and docs presence.
- `docs/plans/progress.md` — recorded M13 implementation and verification evidence.

**Tests:** `uv run pytest tests/test_web.py tests/test_api.py::test_api_does_not_import_privileged -q` — 38 passed, 1 StarletteDeprecationWarning; `uv run pytest tests/test_web.py tests/test_api.py tests/test_security.py -q` — 180 passed, 1 StarletteDeprecationWarning; `uv run pytest -q` — 575 passed, 1 StarletteDeprecationWarning; `uv run ruff check .` — all checks passed; `uv run python -m build` — sdist and wheel built successfully; wheel/sdist manifest smoke verified `odooctl/web/dist/index.html`, `app.js`, `style.css`, and `odooctl/web/README.md` are packaged.
**Result:** M13 Web UI MVP implemented: `odooctl serve` now serves the packaged static SPA by default; UI reads/enqueues/streams only via API endpoints; projects, environment detail, status/doctor/backups/operations, clone/promote, typed confirmations, RBAC display gating, and streaming logs are covered by docs and tests.
**Implementation commit SHA:** `c370d0c`
**Push status:** succeeded — pushed implementation commit `c370d0c` and progress commit `df776e7` to `origin/master`.
**Blockers:** none.
**Next step:** M13 review gate (`t_cddc7524`).

### 2026-05-31 02:07 UTC — M12 security re-review approved

**Changed files:**
- `docs/plans/progress.md` — recorded the M12 security re-review approval, verification evidence, non-blocking notes, and next milestone.

**Review scope:** `811b4bf` (M12 API/runner implementation plus protected-env RBAC remediation).
**Tests:** Claude Code Opus read-only security re-review — approved with no blocking findings; focused protected-env RBAC regressions `uv run pytest tests/test_api.py::test_operator_cannot_enqueue_destructive_op_on_protected_env tests/test_api.py::test_admin_can_enqueue_destructive_op_on_protected_env tests/test_runner.py::test_runner_rejects_protected_destructive_op_with_operator_role -q` — 3 passed, 1 StarletteDeprecationWarning; `uv run pytest tests/test_security.py tests/test_api.py tests/test_runner.py -q` — 164 passed, 1 StarletteDeprecationWarning; `uv run ruff check odooctl/api odooctl/runner odooctl/security tests/test_api.py tests/test_runner.py tests/test_security.py` — all checks passed.
**Result:** Approved — the prior protected-environment RBAC blocker is remediated. API enqueue resolves target environment protection before authorization, passes `protected=...` to RBAC, and signs principal roles into scoped capability tokens; the privileged runner verifies token scope/signature, reconstructs a token-derived principal, independently recomputes protected status, and re-checks RBAC before nonce consumption, lock acquisition, or dispatch.
**Reviewed commit SHA:** `811b4bf`
**Review progress commit SHA:** `08d8f7f`
**Push status:** succeeded — pushed M12 security approval progress commit `08d8f7f` to `origin/master`.
**Blockers:** none.
**Non-blocking follow-ups for later:** gate `POST /operations/{id}/cancel` behind a write/operator-level policy rather than read-family `Action.OPERATIONS`; add project/org scoping for operation reads before any shared/multi-tenant deployment; consider shorter runner capability TTL, nonce-store pruning, and documenting the dual API+runner protected-env enforcement invariant.
**Next step:** M13 Web UI MVP (`t_bf02e8bf`) may proceed after this review progress entry is committed and pushed.

### 2026-05-31 02:01 UTC — Hourly Kanban manager check

- Active task(s): `t_c8f027f4` — **M12 security review** assigned to `odoo-security`; status `running` after this manager pass closed the remediation handoff and re-dispatched the review worker.
- Done since last run: `t_c68f5587` — **M12 protected-env RBAC remediation** is now manager-approved/closed. The blocker was manager-resolvable because the backend worker had already pushed the fix, included exact regression coverage, and left no unresolved product/policy questions.
- Board status: `done=14`, `running=1`, `blocked=0`, `ready=0`, `todo=6` after dispatch. Milestone order remains intact: M12 security review is the only active card before M13 `t_bf02e8bf` can promote.
- Current repo state: branch `master`; `HEAD` `811b4bf` (`docs: record M12 RBAC remediation push`); `origin/master` matches local `HEAD` (`ahead/behind = 0/0`); worktree clean before this progress update.
- Tests/result: manager reran `uv run pytest tests/test_api.py::test_operator_cannot_enqueue_destructive_op_on_protected_env tests/test_api.py::test_admin_can_enqueue_destructive_op_on_protected_env tests/test_runner.py::test_runner_rejects_protected_destructive_op_with_operator_role -q` — 3 passed, 1 StarletteDeprecationWarning; `uv run pytest tests/test_security.py tests/test_api.py tests/test_runner.py -q` — 164 passed, 1 StarletteDeprecationWarning; `uv run ruff check odooctl/api/routes_operations.py odooctl/runner/worker.py tests/test_api.py tests/test_runner.py` — passed.
- Push status: no new milestone-code push existed before this manager progress update; repo was already synced to `origin/master` at `811b4bf`. GitHub auth remains healthy (`gh auth status` OK; `gh auth setup-git` succeeded).
- Blockers: none currently on the board. The prior remediation handoff did not require Rami input because the required action was a procedural approval/re-dispatch step backed by passing local verification and a synced remote state.
- Auto-resolved this run: completed `t_c68f5587` with a manager approval summary/metadata, unblocked `t_c8f027f4`, ran `hermes kanban --board odooctl dispatch`, and verified the security review respawned as run `#37`. This was safe because the child task explicitly required an independent re-review rather than a user decision.
- Next step: let `odoo-security` finish `t_c8f027f4`; if it approves M12, verify M13 Web UI MVP `t_bf02e8bf` promotes/spawns next.

### 2026-05-31 01:13 UTC — M12 protected-env RBAC remediation

**Changed files:**
- `odooctl/api/routes_operations.py` — loads the project context and resolves the target environment before enqueue authorization, passes `protected=ctx.config.is_protected(body.environment)` into RBAC, and embeds principal roles in runner capability tokens.
- `odooctl/runner/worker.py` — reconstructs a token-derived principal from claimed queue-entry capability claims and re-checks the protected-env RBAC floor before nonce consumption, lock acquisition, or dispatch.
- `tests/test_api.py` — added regressions proving operator API tokens receive 403 for destructive operations on protected environments while admin tokens can enqueue.
- `tests/test_runner.py` — added a protected target fixture and runner regression proving a forged/malformed protected destructive entry with only operator roles is rejected before dispatch.
- `docs/plans/progress.md` — recorded remediation evidence and push hygiene.

**Tests:** RED focused run before production fix: `uv run pytest tests/test_api.py::test_operator_cannot_enqueue_destructive_op_on_protected_env tests/test_api.py::test_admin_can_enqueue_destructive_op_on_protected_env tests/test_runner.py::test_runner_rejects_protected_destructive_op_with_operator_role -q` — 1 failed, 2 passed (operator protected clone returned 202 instead of 403); GREEN focused run after fix — 3 passed, 1 StarletteDeprecationWarning; `uv run pytest tests/test_security.py tests/test_api.py tests/test_runner.py -q` — 164 passed, 1 StarletteDeprecationWarning; `uv run ruff check odooctl/api/routes_operations.py odooctl/runner/worker.py tests/test_api.py tests/test_runner.py` — all checks passed; `uv run pytest -q` — 538 passed, 1 StarletteDeprecationWarning.
**Result:** Remediated the `t_c8f027f4` blocking finding: protected-env destructive enqueue now enforces the M11 admin+ floor in the API, and the privileged runner defensively rejects protected destructive entries whose token roles do not meet the same floor before dispatching work.
**Implementation commit SHA:** `ddf17b2`
**Push status:** succeeded — pushed remediation commit `ddf17b2` and progress commit `8544b42` to `origin/master`.
**Blockers:** none for remediation; handoff should return to the M12 security review gate for independent verification.
**Next step:** re-run/unblock `t_c8f027f4` so `odoo-security` can review the protected-env RBAC fix before M13 starts.

### 2026-05-31 00:57 UTC — Hourly Kanban manager check

- Active task(s): `t_c68f5587` — **M12 protected-env RBAC remediation** assigned to `odoo-backend`; status `running` after this manager pass spawned the backend fix task. `t_c8f027f4` remains **blocked** as the security review gate pending the remediation result.
- Done since last run: no additional cards completed. The new board movement is the manager-created remediation lane required to clear the M12 blocker without waiting for user input.
- Board status: `done=13`, `running=1`, `blocked=1`, `ready=0`, `todo=6` after dispatch. Milestone order remains intact: M12 remediation/review is the only active work before M13 `t_bf02e8bf` can promote.
- Current repo state: branch `master`; `HEAD` `61ce614` (`docs: record M12 security review blocker`); `origin/master` matches local `HEAD` (`ahead/behind = 0/0`); worktree clean before this progress update.
- Tests/result: no new manager-run repo tests this tick. Verified blocker evidence from `t_c8f027f4`: `uv run pytest tests/test_security.py tests/test_api.py tests/test_runner.py -q` — 161 passed, 1 StarletteDeprecationWarning; `uv run ruff check odooctl/api odooctl/runner odooctl/security tests/test_api.py tests/test_runner.py tests/test_security.py` — passed; direct RBAC probe reproduced the protected-env authorization gap.
- Blockers: `t_c8f027f4` remains a real implementation blocker, not a user-decision blocker. Rami input is not needed yet because the required next step is concrete backend remediation already defined by the security review.
- Auto-resolved this run: created `t_c68f5587` (**M12 protected-env RBAC remediation**) assigned to `odoo-backend`, linked it as a parent of `t_c8f027f4`, commented the review task with the recovery plan, ran `hermes kanban --board odooctl dispatch`, and verified the backend worker spawned. This was safe because the blocker was actionable engineering work within M12, with a clear fix/test shape and no product/policy ambiguity.
- Next step: let `odoo-backend` finish `t_c68f5587`, then re-run/unblock `t_c8f027f4` so `odoo-security` can verify the fix and either approve M12 or report any remaining issue.

### 2026-05-31 00:00 UTC — M12 security review blocked

**Changed files:**
- `docs/plans/progress.md` — recorded the M12 security-review blocker and verification evidence.

**Review scope:** `dad913a` (M12 API/runner implementation and progress commits).
**Tests:** Claude Code Opus read-only security review — not approved; `uv run pytest tests/test_security.py tests/test_api.py tests/test_runner.py -q` — 161 passed, 1 StarletteDeprecationWarning; direct RBAC probe confirmed `operator` is denied `clone` on protected env when `protected=True` but the enqueue-style `rbac.require(principal, Action.CLONE)` allows it; `uv run ruff check odooctl/api odooctl/runner odooctl/security tests/test_api.py tests/test_runner.py tests/test_security.py` — all checks passed.
**Result:** Blocked — `POST /projects/{project}/operations` performs the base role/action check without passing the target environment's `protected` flag, so an operator API token can enqueue destructive operations such as `clone` against a protected environment despite the M11 admin+ protected-environment floor. Runner token verification checks signature/scope/nonce but does not re-assert RBAC, so it cannot recover the missing access-control check.
**Blocking finding:** `odooctl/api/routes_operations.py:98-101` should load the project context first, resolve `ctx.config.environments[body.environment].protected`, and call `rbac.require(principal, action, protected=...)`; the privileged runner should also defensively re-check protected RBAC before dispatching a claimed queue entry.
**Blockers:** Protected-environment RBAC floor is not enforced in the API/runner mutation path.
**Next step:** backend/security remediation for the protected-environment enqueue/runner re-check, with regression tests proving operator tokens receive 403 for destructive operations on protected envs while admin tokens still enqueue successfully.

### 2026-05-30 23:55 UTC — Hourly Kanban manager check

- Active task(s): `t_c8f027f4` — **M12 security review** assigned to `odoo-security`; status `running` after this manager pass cleared the parent M12 review-required handoff and dispatched the child review gate.
- Done since last run: `t_3aa785d8` — **M12 API and runner** is now manager-approved/closed. The blocker was manager-resolvable because it was only a procedural review-required gate: the worker had already pushed `origin/master` at `dad913a`, provided explicit passing verification evidence, and left no open user/product/policy questions.
- Board status: `done=13`, `running=1`, `blocked=0`, `ready=0`, `todo=6` after dispatch. Milestone order remains intact: M12 security review is the only active card before M13 `t_bf02e8bf` can promote.
- Current repo state: branch `master`; `HEAD` `dad913a` (`docs: record M12 push status`); `origin/master` matches local `HEAD` (`ahead/behind = 0/0`); worktree clean before this progress update.
- Tests/result: manager reran `uv run pytest tests/test_security.py tests/test_api.py tests/test_runner.py -q` — 161 passed, 1 StarletteDeprecationWarning. Verified worker evidence for the closed M12 parent handoff: `uv run pytest -q` — 535 passed; `uv run ruff check .` — passed; `uv run python -m build` — succeeded; `uv run odooctl security runner-check` — contract OK; read-only Claude Opus review — approved.
- Push status: no new milestone-code push existed before this progress update; repo was already synced to `origin/master` at `dad913a`.
- Blockers: none on the board. The M12 parent handoff did not require Rami input because it contained a complete pushed implementation, explicit test/build/review evidence, and no unresolved security/product decisions.
- Auto-resolved this run: completed `t_3aa785d8` with a manager approval summary/metadata, then ran `hermes kanban --board odooctl dispatch` and verified child `t_c8f027f4` promoted and spawned.
- Next step: let `odoo-security` finish `t_c8f027f4`; if it clears, verify M13 Web UI MVP `t_bf02e8bf` promotes/spawns next.

### 2026-05-30 — M12 API and runner implemented

**Changed files:**
- `pyproject.toml` — added `api` optional extras: `fastapi>=0.111`, `uvicorn>=0.29`, `httpx>=0.27`.
- `odooctl/security/tokens.py` — added `**extra_claims` to `mint()` so API session tokens can embed `roles=["viewer"]` or `roles=["operator"]` for RBAC; backward-compatible.
- `odooctl/commands/security.py` — added repeatable `--role` to `security token mint` so operators can mint API session tokens with explicit RBAC roles.
- `odooctl/api/__init__.py` — package init; documents the unprivileged API/runner split.
- `odooctl/api/queue.py` — `QueueEntry` dataclass + `OperationQueue` class: file-backed durable queue in `{state_dir}/queue/`; atomic temp-file enqueue, atomic POSIX rename claim, cancel removal, and corrupt-entry quarantine.
- `odooctl/api/auth.py` — FastAPI bearer-token dependency (`get_principal`), RBAC dependency factory (`require_action`); requires `act="api"` session tokens and extracts roles from token payload.
- `odooctl/api/routes_projects.py` — read-only routes: `GET /projects`, `GET /projects/{p}`, `GET /projects/{p}/environments`, `GET /projects/{p}/status` (metadata-derived, no Docker), `GET /projects/{p}/backups`, `GET /projects/{p}/audit`; no privileged imports.
- `odooctl/api/routes_operations.py` — `POST /projects/{p}/operations` (enqueue with redacted params + capability token), `GET /operations/{id}`, `GET /operations/{id}/events` (SSE, `?max_polls`), `POST /operations/{id}/cancel`; RBAC per operation kind.
- `odooctl/api/app.py` — `create_app(api_key, registry_loader, allowed_hosts, static_dir)` factory; `TrustedHostMiddleware` defaults to localhost-only; optional static SPA mount.
- `odooctl/runner/__init__.py` — package init; documents privileged status.
- `odooctl/runner/worker.py` — `NonceStore` (consumed nonce tracking at `{state_dir}/consumed_nonces.json`), `RunnerWorker.claim_and_run()` (verifies token, checks nonce replay, skips cancelled claimed ops, acquires env lock, dispatches to service, transitions status QUEUED→RUNNING→SUCCEEDED/FAILED, appends audit entry), `RunnerWorker.run_loop(once)`.
- `odooctl/commands/serve.py` — `odooctl serve --host --port --api-key --static-dir --reload`.
- `odooctl/commands/runner.py` — `odooctl runner --once --api-key`.
- `odooctl/main.py` — registered `serve` and `runner` commands.
- `tests/test_security.py` — 7 extra-claim/CLI role tests covering API session token RBAC claims, reserved-claim rejection, and backwards-compatible minting without roles.
- `tests/test_api.py` — 24 TDD tests: 401/403 auth/RBAC (unauthenticated, invalid, expired, non-API token, viewer vs operator), project/env/status/backup routes, enqueue backup/clone, operation record fetch, SSE stream headers, param redaction, queue file persistence/atomic write/cancel/corrupt quarantine, capability token in queue entry, runner contract check (`find_violations`).
- `tests/test_runner.py` — 16 TDD tests: queue enqueue/claim/rename/complete/fail/roundtrip, runner backup execution, tampered-token rejection, nonce consumption, replayed-nonce rejection, cancelled claimed-op skip, empty-queue returns False, service-error marks FAILED, `--once` processes single item.
- `docs/api.md` — API routes, RBAC table, auth format, SSE format, queue format, security model.

**M11 follow-ups addressed:**
- Central redaction wired: `routes_operations.py` calls `redact(body.params)` before writing to operation store or queue.
- Runner token consumption explicit: `NonceStore` in `worker.py` marks nonces consumed; runner rejects replayed nonces with FAILED status + error message.
- Runner contract static check: `test_api_does_not_import_privileged` in `test_api.py` calls `find_violations(("odooctl.api",))` and asserts zero violations.

**Tests:** `uv run pytest tests/test_security.py tests/test_api.py tests/test_runner.py -q` — 161 passed; `uv run pytest -q` — 535 passed; `uv run ruff check .` — all checks passed; `uv run python -m build` — sdist and wheel built successfully; `uv run odooctl security runner-check` — contract OK.
**Result:** M12 acceptance criteria met — API lists projects/envs/status, enqueues backup/clone, runner executes queued operations, event streaming works (SSE), API is localhost-only by default and can serve static SPA, unauthenticated request returns 401, viewer token cannot enqueue mutating operation (403).
**Implementation commit SHA:** `dafd009`
**Push status:** succeeded — pushed implementation commit `dafd009` and progress commit `1d63fd3` to `origin/master`.
**Blockers:** none.
**Next step:** M12 review gate, then M13 Web UI MVP.

### 2026-05-30 22:59 UTC — M11 review gate approved

**Changed files:**
- `docs/plans/progress.md` — recorded the M11 review-gate approval, verification checks, push hygiene, and next milestone.

**Review scope:** `5f87365..7a42d64` (M11 security architecture implementation and progress commits).
**Tests:** Claude Code read-only security review — approved with no blocking findings; `uv run pytest tests/test_security.py -q` — 113 passed; `uv run pytest -q` — 487 passed; `uv run ruff check .` — all checks passed; `uv run python -m build` — sdist and wheel built successfully; CLI/security smokes: `uv run odooctl security runner-check` — contract OK, token mint→verify roundtrip with scoped action/env/project — passed, secret put/list metadata plus disk plaintext grep — passed.
**Result:** M11 review gate approved — RBAC role/action matrix, protected-environment escalation, secret store encryption/file permissions/value egress rules, capability-token signature/scope/expiry behavior, central redaction helpers, and static API/web vs privileged-runner import contract are sufficient for milestone closeout.
**Reviewed commit SHA:** `7a42d64`
**Review progress commit SHA:** `5352585`
**Push status:** succeeded — pushed review-gate progress commits (`5352585`, `4cfd619`) plus this push-status update to `origin/master`; ahead/behind `0/0` after push.
**Blockers:** none. Non-blocking follow-ups for M12: wire central redaction at the operation/audit choke point before user-supplied API params are recorded; make runner token consumption/RBAC minting obligations explicit; consider expanding the static runner contract to catch privileged service imports with an allowlist for read-only services.
**Next step:** start M12 API and runner (`t_3aa785d8`).

### 2026-05-30 22:54 UTC — Hourly Kanban manager check

- Active task(s): `t_d747ede5` — **M11 review gate** assigned to `odoo-reviewer`; status `running` after this manager pass cleared the parent M11 review-required handoff and dispatched the child review gate.
- Done since last run: `t_c76c65a1` — **M11 security architecture** is now manager-approved/closed. The blocker was manager-resolvable because it was only a procedural review-required gate: the worker had already pushed `origin/master` at `7a42d64`, provided explicit test/build evidence, and left no open questions or user-needed decisions.
- Board status: `done=11`, `running=1`, `blocked=0`, `ready=0`, `todo=8` after dispatch. Milestone order remains intact: M11 review gate is the only active card before M12 `t_3aa785d8` can promote.
- Current repo state: branch `master`; `HEAD` `7a42d64` (`docs: record M11 security push status`); `origin/master` matches local `HEAD` (`ahead/behind = 0/0`); worktree clean before this progress update.
- Tests/result: manager reran `uv run pytest tests/test_security.py -q` — 113 passed. Verified worker evidence for the closed M11 parent handoff: `uv run pytest -q` — 487 passed; `uv run ruff check .` — passed; `uv run python -m build` — succeeded.
- Push status: no new milestone-code push existed before this progress update; repo was already synced to `origin/master` at `7a42d64`.
- Blockers: none on the board. The M11 parent handoff did not require Rami input because it contained a complete pushed implementation, explicit verification evidence, and no unresolved product/policy/security questions.
- Auto-resolved this run: completed `t_c76c65a1` with a manager approval summary/metadata, then ran `hermes kanban --board odooctl dispatch` and verified child `t_d747ede5` promoted and spawned.
- Next step: let `odoo-reviewer` finish `t_d747ede5`; if it clears, verify M12 API and runner `t_3aa785d8` promotes/spawns next.

### 2026-05-30 — M11 security architecture implemented

**Changed files:**
- `odooctl/security/__init__.py` — new package; re-exports principals/RBAC surface and documents the enforced security rules.
- `odooctl/security/principals.py` — `Org`/`User`/`Role`/`Principal`/`PrincipalKind` identity models; role privilege ordering (`viewer<operator<admin<owner`), `has_at_least`, `identity` string for audit, transport-agnostic for future API use.
- `odooctl/security/rbac.py` — `Action` enum (read/status/logs/backups/operations/audit + backup/deploy/clone/restore/promote/env/secrets); `ROLE_ACTIONS` matrix; `is_allowed`/`require`/`allowed_actions`/`role_matrix`; protected/production destructive escalation (admin+ required); `AccessDenied` exception (names principal+action, no secrets).
- `odooctl/security/secrets.py` — stdlib-only secret store: `SecretValue` (repr/str masked, `.reveal()` only), encrypt-then-MAC HMAC-SHA256 keystream `encrypt`/`decrypt`, `derive_key` (PBKDF2), `SecretRecord` rotation metadata, `SecretStore` (put/put_reference/get/rotate/delete/list/metadata, env-ref + encrypted sources, 0600 atomic writes), `resolve_key`/`open_store`/`default_store_path`.
- `odooctl/security/tokens.py` — capability tokens (`base64url(header).payload.HMAC-SHA256`); `mint`/`verify`/`decode_unverified`; scope (action/env/project), expiry, optional subject, random nonce; `TokenInvalid`/`TokenExpired`/`TokenScopeError`.
- `odooctl/security/redaction.py` — `strip_env_defaults` (collapses `${VAR:-default}`→`${VAR}`), `redact_text`, recursive `redact` for str/dict/list; masks known secret values and secret-looking keys.
- `odooctl/security/runner_contract.py` — AST-based `scan_source_for_violations`/`find_violations`/`assert_api_does_not_import_privileged`; privileged prefixes `odooctl.adapters`/`odooctl.odoo`; API packages `odooctl.api`/`odooctl.web` (tolerates missing packages today, catches future direct imports); documents API vs runner capability lists.
- `odooctl/commands/security.py` — `odooctl security rbac` (matrix display), `security secret put/get/rotate/list` (values via `--value-env`/`--stdin`/`--reference` only — never argv; `get` reveals only with `--reveal`), `security token mint/verify` (key from `--key-env`), `security runner-check`.
- `odooctl/main.py` — registered `security` sub-app.
- `tests/test_security.py` — 113 tests: full role×action matrix, protected escalation, secret crypto roundtrip/tamper/wrong-key/private file modes, store no-leak (repr/disk/metadata)/rotation/env-ref, redaction (incl. `${VAR:-default}` and non-string secret-key values), token mint/verify/tamper/expiry/scope/CLI stdin + empty-key guard, runner-contract absolute+relative import scan + assert-on-violation, plus redacted params safe in operation/audit surfaces and audit tamper-detection still fires.
- `docs/rbac.md`, `docs/runner-architecture.md` — security model, RBAC matrix, secret handling, capability tokens, token replay-window caveat, local key threat model, and web/API-vs-runner split.

**Tests:** `uv run pytest tests/test_security.py -q` — 113 passed; `uv run pytest -q` — 487 passed; `uv run ruff check .` — all checks passed; `uv run python -m build` — sdist and wheel built successfully (wheel includes `odooctl/security/*` and `odooctl/commands/security.py`); CLI smoke (in `/tmp` with `--state-dir`): rbac matrix shows `operator.deploy=True`/`operator.secrets=False`; secret put/list/get confirmed no value in metadata output and no plaintext on disk, `--reveal` prints value; token mint→verify roundtrip ok, wrong-scope verify exits 1 with `INVALID: token not valid for action 'restore'`; `runner-check` reports contract OK.
**Result:** M11 security primitives implemented — RBAC policy helpers for future API/runner enforcement, encrypted/env-referenced secret store with rotation metadata and private file creation, signed scoped capability tokens with explicit replay-window caveat, central redaction, and a structural API-vs-runner import contract that catches absolute and relative privileged imports. No new runtime dependency (stdlib-only crypto). Existing CLI remains backward-compatible; no config-compatibility breakage.
**Implementation commit SHA:** `3119913`
**Push status:** succeeded — pushed implementation commit `3119913` and progress commit `df4e4d1` to `origin/master`; ahead/behind `0/0` after push.
**Blockers:** none.
**Next step:** M11 review gate, then M12 API and runner. Note for M12: when `odooctl/api` / `odooctl/web` land, `tests/test_security.py::test_find_violations_no_api_package_yet` plus `odooctl security runner-check` enforce the no-privileged-import contract.

### 2026-05-30 — M10 docs review approved

**Changed files:**
- `docs/catalog.md` — corrected `catalog list` command comment from "(bundled + session-loaded)" to "(bundled only)"; `catalog list` has no `--catalog` flag so user manifests never appear in its output — the prior comment was misleading.
- `docs/plans/progress.md` — recorded M10 docs review result.

**Review scope:** `docs/catalog.md`, `docs/plans/m10-onboarding-catalog.md`, `odooctl/catalog/` package, `odooctl/commands/catalog.py`, `odooctl/commands/setup.py`, `tests/test_catalog.py`, `tests/test_setup.py`, `tests/test_cli_smoke.py`.
**Checks:**
- Schema fields and validators match docs tables for `StackTemplate`, `AddonSource`, `AddonPack`, `CompanionService`.
- Bundled manifest content (`odoo-18-community.yaml`, `odoo-19-community.yaml`, `oca-web.yaml`, `companions.yaml`) matches the docs tables for images, versions, ports, and IDs.
- Setup integration examples (`--yes`, `--stack`, `--catalog`, `--name`) match `setup.py` CLI parameters.
- User-manifest YAML examples in docs parse correctly per the schema.
- Safety rules in docs accurately reflect schema validators (no `:latest`, env-var-name-only `auth_env`).
- Manifest schema reference tables match Pydantic model fields.
- `uv run pytest tests/test_catalog.py tests/test_setup.py tests/test_cli_smoke.py -q` — 80 passed.
**Result:** M10 docs review approved — one inaccurate comment corrected; all examples, field tables, and safety rules are coherent with the implementation.
**Commit SHA:** `5f87365`
**Push status:** succeeded — pushed `5f87365` to `origin/master`.
**Blockers:** none
**Next step:** M11 security architecture (`t_c76c65a1`).

### 2026-05-30 21:52 UTC — Hourly Kanban manager check

- Active task(s): `t_e86d60c8` — **M10 docs review** assigned to `odoo-docs`; status `running` after this manager pass verified and closed the M10 parent handoff, then dispatched the child task.
- Done since last run: `t_3a860c0f` — **M10 onboarding catalog** is now manager-approved/closed. The prior blocker was manager-resolvable because the worker handoff already included a clean synced repo, pushed `origin/master` at `2f78d9e`, passing full-suite test/ruff/build evidence, setup/validate smoke output, and a read-only review approval with no open questions.
- Board status: `done=9`, `running=1`, `blocked=0`, `ready=0`, `todo=10` after dispatch. Milestone order remains intact: M10 docs review is the only active card before M11 `t_c76c65a1` can promote.
- Current repo state: branch `master`; `HEAD` `2f78d9e` (`docs: clarify M10 push status`); `origin/master` matches local `HEAD` (`ahead/behind = 0/0`); worktree clean before this progress update.
- Tests/result: no new manager-run repo tests this tick. Verified worker evidence for the closed M10 parent handoff: `uv run pytest -q` — 374 passed; `uv run ruff check .` — passed; `uv run python -m build` — succeeded; `uv run odooctl setup --yes --stack odoo-18-community --name catalog-smoke --output <tmp>/odooctl.yml && uv run odooctl validate --config <tmp>/odooctl.yml` — passed with the expected missing `ODOO_DB_PASSWORD` warning; read-only Claude review — approved with no blocking issues.
- Push status: no new code or manager push existed before this progress update; repo was already synced to `origin/master` at `2f78d9e`.
- Blockers: none on the board. The M10 parent handoff did not require Rami input because it was only a procedural review-required gate and the manager independently verified the cited evidence against live repo/board state before closing it.
- Next step: let `odoo-docs` finish `t_e86d60c8` (M10 docs review), then verify whether M11 security architecture `t_c76c65a1` promotes and spawns.

### 2026-05-30 20:41 UTC — M10 onboarding catalog implemented

**Changed files:**
- `odooctl/catalog/__init__.py`, `schema.py`, `registry.py`, `render.py` — added typed catalog entry models, manifest loading/lookup, validation for pinned images/env-var auth references, and stack-template config rendering.
- `odooctl/catalog/manifests/odoo-19-community.yaml`, `odoo-18-community.yaml`, `oca-web.yaml`, `companions.yaml` — added bundled Odoo stack templates, OCA addon sources/packs, and companion service templates.
- `odooctl/commands/catalog.py`, `odooctl/main.py` — added `odooctl catalog list/show/add` and registered the catalog subcommand.
- `odooctl/commands/setup.py` — wired setup scaffolding to bundled catalog templates and per-invocation user manifest extension via `--catalog PATH`, while preserving legacy stack IDs.
- `tests/test_catalog.py` — added schema, registry, render, CLI, setup integration, validation, user-manifest, and root CLI registration coverage.
- `docs/catalog.md` — documented catalog commands, manifest schema, bundled entries, setup integration, user extension, and safety rules.
- `docs/plans/progress.md` — recorded M10 implementation status.

**Tests:** `uv run pytest tests/test_catalog.py tests/test_setup.py -q` — 54 passed; `uv run pytest tests/test_catalog.py tests/test_setup.py tests/test_cli_smoke.py -q` — 80 passed; `uv run ruff check odooctl/catalog odooctl/commands/catalog.py odooctl/commands/setup.py odooctl/main.py tests/test_catalog.py` — all checks passed; smoke `uv run odooctl setup --yes --stack odoo-18-community --name catalog-smoke --output <tmp>/odooctl.yml && uv run odooctl validate --config <tmp>/odooctl.yml` — config valid with expected missing `ODOO_DB_PASSWORD` warning; `uv run pytest -q` — 374 passed; `uv run ruff check .` — all checks passed; `uv run python -m build` — sdist and wheel built successfully.
**Result:** M10 catalog implementation is ready for review: bundled and user manifests validate, setup consumes catalog stack templates, catalog CLI lists/shows/validates manifests, custom stack manifests extend setup for a single invocation, and generated config validates.
**Implementation commit SHA:** `3ee8fdf`
**Push status:** succeeded — pushed M10 implementation/progress commits to `origin/master`.
**Blockers:** none
**Next step:** M10 review gate, then M11 security architecture.

### 2026-05-30 20:25 UTC — M9 review gate approved

**Changed files:**
- `docs/plans/progress.md` — recorded the M9 review-gate approval, verification checks, push hygiene, and non-blocking follow-ups.

**Review scope:** `8eee0ff..b1edd45` (M9 environment/branch model implementation, review-fix handoff, and progress commits before this review entry).
**Tests:** Claude Code read-only review — approved; `uv run pytest tests/test_branch_status.py tests/test_promote.py tests/test_env_cmd.py -q` — 51 passed; `uv run pytest -q` — 314 passed; `uv run ruff check .` — all checks passed; `uv run python -m build` — sdist and wheel built successfully; git hygiene check before review entry — branch `master` tracking `origin/master` with clean worktree.
**Result:** M9 review gate approved — environment tier/protected semantics, branch drift reporting, promote preview, production confirmation, pre-backup dirty-worktree guard, target backup before deploy, failed-promote data+code rollback, and `env open` coverage are sufficient for milestone closeout.
**Reviewed commit SHA:** `b1edd45`
**Review progress commit SHA:** `cfa7e01`
**Push status:** succeeded — pushed review-gate progress commit `cfa7e01` to `origin/master`.
**Blockers:** none
**Next step:** start M10 onboarding catalog (`t_3a860c0f`).
**Non-blocking follow-ups for a later milestone:** prefer merging a fresh remote-tracking source ref (for example `origin/<source_branch>`) instead of a possibly stale local source branch during promote; document that code rollback re-runs compose from the reset worktree but does not pin/revert image-baked addons; decide whether `last_deployed_commit` should be written to config or remain metadata-store derived; consider making promote preview warn when fast-forward feasibility is already impossible.

### 2026-05-30 20:13 UTC — Hourly Kanban manager check

- Active task(s): `t_8a3df0ce` — **M9 review gate** assigned to `odoo-reviewer`; status `running` with active worker run `#25` started at 20:12 UTC after the manager-cleared M9 parent handoff promoted it.
- Done since last run: `t_660859dd` — **M9 environment branch model** is now closed/resolved, which promoted and spawned the child review gate `t_8a3df0ce`; no M10 work has started yet, so milestone order remains M6 → M7 → M8 → M9.
- Board status: `done=7`, `running=1`, `blocked=0`, `ready=0`, `todo=12`; no stalled ready cards, and next dependency-gated child remains `t_3a860c0f` (M10 onboarding catalog) behind the M9 review gate.
- Current repo state: branch `master`; `HEAD` `1925fe6` (`docs: update odooctl kanban progress`); `origin/master` matches local `HEAD` (`ahead/behind = 0/0`); worktree clean before this progress update.
- Tests/result: no new manager-run repo tests this tick. Current verified evidence for M9 remains the backend handoff already recorded in this file: milestone subset `uv run pytest tests/test_branch_status.py tests/test_promote.py tests/test_env_cmd.py -q` → 51 passed, `uv run pytest -q` → 314 passed, `uv run ruff check .` → passed, `uv run python -m build` → succeeded.
- Push status: no milestone-code push attempt by the manager this tick before this progress update; repo was already synced to `origin/master` at `1925fe6`.
- Blockers: none currently on the board. The prior review-required blocker was manager-resolvable because the parent task already carried explicit passing tests, commit/push metadata, and a clean synced repo state, so the manager safely advanced it and verified the child review gate actually promoted/spawned.
- Next step: let `odoo-reviewer` finish `t_8a3df0ce`, then verify its completion or any genuine blocker before promoting M10 `t_3a860c0f`.

### 2026-05-30 20:08 UTC — Hourly Kanban manager check

- Active task(s): none running. Board is currently stalled on `t_660859dd` — **M9 environment branch model** assigned to `odoo-backend`; status `blocked` as a review-required handoff.
- Done since last run: no new cards completed. The only board transition since the previous manager check is `t_660859dd` moving from `running` to `blocked` after the backend worker pushed its M9 implementation and requested review.
- Board status: `done=6`, `blocked=1`, `running=0`, `ready=0`, `todo=13`; dispatcher pass promoted/spawned nothing, and child review gate `t_8a3df0ce` remains dependency-gated in `todo` behind the blocked parent.
- Current repo state: branch `master`; `HEAD` `aa53bce` (`docs: update odooctl kanban progress`); `origin/master` matches local `HEAD` (`ahead/behind = 0/0`); worktree was clean before this progress update.
- Tests/result: no new manager-run tests this tick. Current verified M9 handoff evidence on the blocked task is unchanged: `uv run pytest tests/test_branch_status.py tests/test_promote.py tests/test_env_cmd.py -q` → 51 passed, `uv run pytest -q` → 314 passed, `uv run ruff check .` → passed, `uv run python -m build` → succeeded.
- Push status: no milestone code or manager commit existed before this progress update; repo was already synced to `origin/master` at `aa53bce`.
- Exact blocker: `t_660859dd` is blocked with **"review-required: M9 branch/promote/env model implemented and pushed; 314 tests, ruff, build pass; needs review gate before M10."** Worker handoff cites implementation commit `b9280d7`, progress commit `82fe484`, and clean synced state after manager progress commit `aa53bce`. Until this review-required handoff is accepted/completed, child `t_8a3df0ce` (M9 review gate) cannot promote to `ready`.
- Next step: inspect and accept/close the `t_660859dd` review-required handoff, then verify `t_8a3df0ce` promotes to `ready`/`running` for the M9 review gate before any M10 work begins.

### 2026-05-30 19:47 UTC — Hourly Kanban manager check

- Active task(s): `t_660859dd` — **M9 environment branch model** assigned to `odoo-backend`; status `running` with active worker run `#23`.
- Done since last run: `t_242010a5` — M8 safety/security review cleared its review-required handoff, which promoted M9 and spawned the backend worker; no new completed cards after M9 started.
- Board status: `done=6`, `running=1`, `blocked=0`, `ready=0`, `todo=13`; no stalled ready cards, and the next child gate remains dependency-linked as `t_8a3df0ce` (M9 review gate).
- Current repo state: branch `master`; `HEAD` `8eee0ff` (`docs: update odooctl kanban progress`); `origin/master` matches local `HEAD` (`ahead/behind = 0/0`); worktree is **dirty because the active M9 worker has local implementation changes in progress** (`odooctl/config.py`, `odooctl/main.py`, `odooctl/operations/models.py`, `odooctl/services/models.py`, `odooctl/commands/env.py`, new `branch.py`/`promote.py` command+service files, related tests, and this progress file).
- Tests/result: no new manager-run tests this tick. Current evidence comes from the active M9 worker handoff-in-progress: initial implementation plus review-fix pass recorded in `docs/plans/progress.md` with `uv run pytest tests/test_branch_status.py tests/test_promote.py tests/test_env_cmd.py -q` → 51 passed, `uv run pytest -q` → 314 passed, `uv run ruff check .` → passed, `uv run python -m build` → passed.
- Push status: manager has not attempted a push for milestone code this tick because the M9 worker has not finished/committed yet; GitHub CLI auth is healthy for `Rami-0` and ready when the worker or manager needs to push.
- Blockers: none on the board right now. The only live constraint is that M10+ remain dependency-gated until `t_660859dd` completes and promotes `t_8a3df0ce`.
- Next step: let `odoo-backend` finish `t_660859dd`, verify its final commit/push metadata, then confirm `t_8a3df0ce` promotes to `ready`/`running` for the M9 review gate before advancing to M10.

### 2026-05-30 — M9 review findings fixed (blocking)

**Changed files:**
- `odooctl/services/promote.py` — (1) replaced `git pull --ff-only` with `git merge --ff-only <source_branch>` so source commits are integrated into target before deploy; (2) capture `pre_promote_commit` after checkout/before merge; on failure, added code rollback (`git checkout; git reset --hard pre_promote_commit; compose.up`) alongside data restore; honest error if rollback is incomplete ("Manual intervention required"); (3) added `confirm: bool = False` param — raises RuntimeError if target `is_protected()` and `confirm=False`; preview remains unrestricted; (4) added `_assert_clean_worktree` preflight using module-level `run` (mockable) before backup; raises if `git status --porcelain` shows dirty paths.
- `odooctl/commands/promote.py` — added `yes: bool = False` parameter to `execute()`; passed as `confirm=yes` to `run_promote`.
- `odooctl/main.py` — added `--yes / -y` option to `promote` CLI command.
- `tests/test_promote.py` — rewrote/extended: added `confirm=True` to all existing tests that reach past env-var preflight; updated run mocks to accept `**kwargs`; updated ordering assertion in `test_run_promote_preflight_and_backup_before_git_operations` to include `git:status` before `backup`; renamed `test_run_promote_deploy_uses_target_branch` → `test_run_promote_merges_source_into_target_via_ff_only` with merge assertions; added 10 new tests covering: protected-target enforcement, `--yes` bypass, preview allowed without confirm, dirty-worktree abort, code rollback resets to pre_promote_commit, code rollback redeploys, honest incomplete-rollback error (data restore failure), honest incomplete-rollback error (code reset failure), CLI `--yes` enforcement, CLI `--yes` success flow.
- `tests/test_env_cmd.py` — added 5 tests for `env open`: refuses reserved names (production, staging), refuses duplicate env, `--no-provision` writes config without clone, provision clones sanitized from source.

**Tests:** `uv run pytest tests/test_branch_status.py tests/test_promote.py tests/test_env_cmd.py -q` → 51 passed; `uv run pytest -q` → 314 passed; `uv run ruff check .` → all checks passed; `uv run python -m build` → sdist and wheel built successfully.
**Result:** All 5 blocking review findings resolved — source code is now integrated via ff-merge before deploy; rollback restores both data and code with honest error surfacing on partial failure; protected production requires explicit confirmation (preview remains free); dirty-worktree is caught before backup; `env open` has full CLI test coverage.
**Implementation commit SHA:** `b9280d7`
**Push status:** succeeded — pushed `b9280d7` to `origin/master`.
**Blockers:** none
**Next step:** M9 review gate, then M10 onboarding catalog.

### 2026-05-30 — M9 environment/branch model implemented

**Changed files:**
- `odooctl/config.py` — added `tier`, `protected`, `promotes_to`, `auto_deploy`, `last_deployed_commit` fields to `EnvironmentConfig`; added `promotes_to` validator in `validate_environment_graph`; added `is_protected(name)` method to `OdooCtlConfig`.
- `odooctl/operations/models.py` — added `PROMOTE = "promote"` to `OperationKind`.
- `odooctl/services/models.py` — added `BranchStatus` and `PromoteResult` dataclasses.
- `odooctl/services/branch.py` — new: `get_branch_statuses()` service; git-based per-environment drift detection (`_git_rev`, `_git_count`, `_compute_drift`).
- `odooctl/services/promote.py` — new: `promote_preview()` (no side effects) and `run_promote()` (source health → backup target → deploy → healthcheck → rollback on failure → record metadata).
- `odooctl/commands/branch.py` — new: `odooctl branch status` CLI; table + JSON output.
- `odooctl/commands/promote.py` — new: `odooctl promote <source> <target> [--preview]` CLI; wraps `run_promote` in `run_operation` for audit/lock.
- `odooctl/commands/env.py` — added `env open <name> --from <branch>` command; creates ephemeral development environment (tier=development) cloned/sanitized from production (or `--from-env`).
- `odooctl/main.py` — registered `branch` sub-app and top-level `promote` command.
- `tests/test_branch_status.py` — new: 17 TDD tests covering BranchStatus dataclass, drift states (clean/ahead/behind/diverged/unknown), tier inference, `is_protected`, `promotes_to` validation, config field acceptance.
- `tests/test_promote.py` — new: 14 TDD tests covering preview no-side-effects, `promotes_to` validation, source health checked before backup, backup before deploy, success/failure metadata recording, rollback on healthcheck failure, branch selection, env-var preflight.

**Tests:** (superseded by review-fixes entry above)
**Result:** M9 initial implementation.
**Implementation commit SHA:** `b9280d7`
**Push status:** succeeded — pushed `b9280d7` to `origin/master`.
**Blockers:** none (resolved in review-fixes entry above)
**Next step:** M9 review gate, then M10 onboarding catalog.

### 2026-05-30 18:45 UTC — Hourly Kanban manager check

- Active task(s): none running; board remains stalled on `t_242010a5` — **M8 safety/security review** assigned to `odoo-security`, status `blocked`.
- Done since last run: no additional Kanban cards completed after the M8 security review handoff and hardening-test push at `27dac21`.
- Board status: `done=5`, `blocked=1`, `running=0`, `ready=0`, `todo=14`; dispatcher pass promoted/spawned nothing.
- Current repo state: branch `master`; `HEAD` `27dac21` (`docs: record M8 security review push status`); worktree clean before this progress update; `master` matches `origin/master` with no ahead/behind.
- Tests/result: no new repo tests run by the manager this tick; relying on the completed M8 security handoff already recorded for `t_242010a5` (`uv run pytest tests/test_import_hardening.py -q` → 7 passed, milestone subset → 58 passed, `uv run pytest -q` → 268 passed, `uv run ruff check .` → passed, `uv run python -m build` → passed).
- Push status: no milestone code changes this tick before the progress update; repo `HEAD` already matched `origin/master` at `27dac21`.
- Exact blocker: `t_242010a5` is intentionally blocked as `review-required` after approval. Latest run summary: **"M8 safety/security review approved and hardening tests pushed at 27dac21; needs human eyes on the tests/progress update before promoting M9."** Until that review-required handoff is accepted/unblocked, child `t_660859dd` (M9 environment branch model) remains dependency-gated in `todo`.
- Next step: inspect and accept the `t_242010a5` review-required handoff, then unblock/complete it so M9 `t_660859dd` can promote to `ready` for `odoo-backend`.

### 2026-05-30 17:52 UTC — M8 safety/security review approved + hardening tests

**Changed files:**
- `tests/test_import_hardening.py` — added explicit M8 safety regression guards proving import detection/preview does not invoke subprocess/shell mutation paths, does not write files, and never stores/renders literal DB password values (including `${VAR:-default}` secrets).
- `docs/plans/progress.md` — recorded the M8 security review result and updated the M8 checklist.

**Review scope:** `a1dc5f8` plus the new hardening tests in this entry.
**Tests:** Claude Code read-only security review — approved; `uv run pytest tests/test_import_hardening.py -q` — 7 passed; `uv run pytest tests/test_import_detect.py tests/test_import_report.py tests/test_import_adopt.py tests/test_import_hardening.py tests/test_setup.py -q` — 58 passed; `uv run pytest -q` — 268 passed; `uv run ruff check .` — all checks passed; `uv run python -m build` — sdist and wheel built successfully.
**Result:** M8 safety contract approved — detection/preview remain file-read-only with no subprocess/Docker/DB/volume mutation path, preview is default, adoption writes config/registry only after explicit `--yes`, secrets are referenced by env-var name only, overwrite requires `--force`, and validate/doctor/backup run after adoption unless explicitly skipped.
**Hardening/review commit SHA:** `f0ca498`
**Push status:** succeeded — pushed `f0ca498` to `origin/master` after configuring the repo credential helper to use the authenticated `/home/dev` GitHub CLI account.
**Blockers:** none found in the M8 safety contract. Informational follow-ups for later: consider documenting that non-secret DB host/user values are rendered as detected, and decide whether “verified backup” should mean an additional verify command beyond manifest/checksum creation.
**Next step:** M8 review-required handoff for the added hardening tests, then proceed to M9 environment/branch model after approval.

### 2026-05-30 17:44 UTC — Hourly Kanban manager check

- Active task: `t_242010a5` — M8 safety/security review assigned to `odoo-security`; status `running` after this manager pass completed the M8 implementation card and dispatched the child review gate.
- Done since last run: `t_c6eb31b9` — M8 import takeover + setup wizard accepted as complete by manager verification. The blocked `review-required` handoff already had passing verification and synced commits, so the manager closed it and confirmed child promotion.
- Board status: `done=5`, `running=1`, `blocked=0`, `ready=0`, `todo=14` after dispatch.
- Current repo state: branch `master`; `HEAD` `a1dc5f8` (`docs: record M8 push status`); worktree clean; `master` matches `origin/master` with no ahead/behind.
- Tests/result: no new repo tests run by the manager this tick; relied on the verified M8 handoff already recorded for `t_c6eb31b9` (`uv run pytest tests/test_import_detect.py tests/test_import_report.py tests/test_import_adopt.py tests/test_setup.py -q` → 51 passed, `uv run pytest -q` → 261 passed, `uv run ruff check .` → passed, `uv run python -m build` → passed, plus import/setup/adoption smoke checks).
- Push status: no new repo commit this tick before the progress update; existing M8 implementation/progress commits are already synced to `origin/master`.
- Blockers: none currently on the board.
- Next step: let `odoo-security` complete or block `t_242010a5` (M8 safety/security review); only then should M9 environment branch model `t_660859dd` promote.

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

- [x] Add compose/Odoo detector.
- [x] Add import preview report.
- [x] Generate config without redeploy.
- [x] Register imported project.
- [x] Run doctor and verified backup after import.
- [x] Add newcomer `odooctl setup` wizard.
- [x] Verify import against Odoo 19 fixture.
- [x] Add tests enforcing import detection has no mutating command calls.
- [x] Document the import safety contract in CLI help and docs.

### M9 — Environment/branch model ✓ DONE

- [x] Add environment tiers and protected production semantics.
- [x] Add branch status/drift detection.
- [x] Add promote staging → production flow.
- [x] Add ephemeral branch/dev environment flow.
- [x] Add rollback-on-failed-promote tests.

### M10 — Onboarding catalog

- [x] Add catalog manifest schema.
- [x] Add bundled Odoo stack templates.
- [x] Add OCA/private/Enterprise addon source model.
- [x] Add companion service templates.
- [x] Wire catalog into setup wizard.

### M11 — Security architecture

- [x] Add org/user/role/principal models.
- [x] Add RBAC action matrix.
- [x] Add secret store and rotation commands.
- [x] Add capability tokens.
- [x] Enforce web/API vs runner privilege split.
- [x] Expand security docs.

### M12 — API and runner ✓ DONE

- [x] Add optional FastAPI service.
- [x] Serve static SPA assets from `odooctl serve`.
- [x] Add durable queue handoff.
- [x] Add privileged runner.
- [x] Add operation event streaming.
- [x] Add API auth/RBAC tests.
- [x] Verify API-driven backup/clone via runner.

### M13 — Web UI MVP

- [x] Add web asset/app structure.
- [x] Projects page.
- [x] Environment detail page.
- [x] Doctor/status/backups/operations views.
- [x] Clone/promote operation buttons.
- [x] Streaming operation logs.
- [x] Verify UI only talks to API.

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
