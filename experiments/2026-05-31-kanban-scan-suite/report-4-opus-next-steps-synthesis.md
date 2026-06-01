# Report 4 — Opus Synthesis: Current State, Failure Points, Next Steps

**Kanban task:** `t_6c5006df`
**Author:** Claude Opus 4.8 (synthesis agent)
**Date:** 2026-06-01
**Repository:** `/home/dev/odooctl`, branch `master`
**Synthesis HEAD (this report):** `659fad9573bd4697f970a45d32ebaff21053cb62`

## Inputs synthesized

1. **Report 1** — Claude Opus 4.8 feature/security scan. Static review, breadth via sub-agents, line-referenced. Commit `9e39a95`. 24 findings (F1–F24). **Did not run the test suite** (relied on a project-memory estimate of "~520 tests").
2. **Report 2** — GPT-5.5 Codex feature/security scan. Static review + focused proof scripts + *partial* test runs. Commit `30d29b0`. 6 findings (F1–F6). Explicitly scope-limited after its breadth sub-scan timed out.
3. **Report 3** — Odoo 18 CE + 19 CE full/api/ctl experiment. **Dynamic**: real disposable Docker stacks (`odoo:18.0`, `odoo:19.0`, `postgres:16`), docker-native DB/filestore, CLI + FastAPI + runner. Commit `97a487a`. Ran the **full** pytest suite.

### Grounding note on commit lineage (verified this session via `git log`)

The three reports were taken at three different commits, but every intervening commit is **docs-only** — each commit merely adds the previous report's markdown:

```
659fad9  docs: add Odoo 18 19 experiment report     ← this synthesis HEAD (adds Report 3)
97a487a  docs: add gpt55 codex security audit        ← Report 3 inspected here (adds Report 2)
30d29b0  docs: add Claude Opus feature security audit ← Report 2 inspected here (adds Report 1)
9e39a95  docs: finalize odooctl progress push status  ← Report 1 inspected here
```

**Consequence:** the *product code* is effectively identical across all three audits and this synthesis. The three reports are therefore three independent looks (two static methods + one dynamic method) at one codebase. Where they agree, that is genuine cross-validation; Report 3's full-suite pytest result applies directly to the exact code Reports 1 and 2 reviewed.

### Evidence classes used in this report

- **[EXEC]** Confirmed by execution — Report 3 runtime, or this session's own read-only `git`/`grep`/file reads.
- **[SRC]** Confirmed by direct source read in this synthesis (labeled; commit `659fad9`).
- **[CONCUR]** Static concern independently reported by **both** Report 1 and Report 2 (high confidence; not demonstrated end-to-end against a live exploit).
- **[SOLO]** Single-source static concern (Report 1 only), unless verified here → then also **[SRC]**.
- **[HYP]** Hypothesis / unexplained observation requiring root-cause work.

> Scope discipline: this is a synthesis/report-writing task. No product code was modified. No deployment, Docker, database, destructive, or network-changing commands were run. The only commands executed were read-only `git log`/`git status`, `grep`, and file reads, used to resolve two decision-critical ambiguities (the release-blocker's root cause and the single-source cancel-RBAC claim). Those are labeled **[SRC]/[EXEC]** below. No secrets are reproduced; the minted API tokens that appear in Report 3 are intentionally not echoed here.

---

## 1. Executive summary

odooctl is a security-aware, well-layered CLI Odoo deployment platform with an optional FastAPI control plane (unprivileged API + durable queue + privileged runner) and a static web UI. The design is genuinely good: list-argument subprocess almost everywhere, HMAC capability tokens (constant-time, no alg-confusion, server-side role re-derivation, runner-side single-use nonces), an encrypt-then-MAC secret store, `yaml.safe_load` throughout, a side-effect-free importer, a flock-guarded hash-chained audit log, and the previously-blocked M12 protected-environment RBAC floor now enforced at *both* the API enqueue layer and the runner.

The synthesis changes the headline in one important way relative to the two static reports:

> **The `master` branch is currently RED.** Report 3's full suite is **14 failed / 709 passed (723 total)** — not the implicitly-green "~520 tests" Report 1 assumed from memory. **All 14 failures share one root cause**: the global `--project` / `--project-dir` selector is not propagated into config resolution, so commands fall back to the cwd and fail with `Config file not found: /home/dev/odooctl/odooctl.yml`. This is both a **reliability** bug (the suite is red) and a **safety** bug (a destructive command can silently target the wrong project/cwd). I verified the root cause in source this session. **This is the release-blocker and the first thing to fix** — you cannot trust test-based verification of any security fix until the suite is green.

Beyond that, the two static reviews **independently agree** on five security themes (high confidence), and Report 3 adds runtime context that *sharpens* two of them:

1. **Unvalidated identifiers at the config boundary** feed three `sh -lc` f-string sinks (DB clone, filestore copy/restore) and the Traefik `Host()` rule. One validator layer closes two findings. Report 3 shows the host lacked `pg_dump`/`psql`, so **docker execution mode is the practical norm** on such operator machines — which makes the docker-mode `sh -lc` clone path the *default-in-practice* path, not an edge case as Report 1's "default is host mode" caveat implied.
2. **Literal `== "production"` guards** instead of the richer `is_protected()` policy, scattered across deploy/clone/db-swap/destroy. Any protected env not literally named `production` loses its backups and refusals.
3. **Drop-before-verify with no rollback** in restore / db-swap / failed-deploy. Report 3 shows the drop→rename swap *mechanism* executing in the restore path (it succeeded; no failure was injected).
4. **DB password on argv** leaking through an unredacted `CommandError` into API-exposed operation errors.
5. **Traefik routing-rule injection** from an unvalidated domain string.

Report 3 also surfaces a **new empirical failure not in either static report**: an **API/runner-enqueued `backup staging` operation failed on both Odoo 18 and 19**, while every CLI operation succeeded — and `runner --once` still exited `0` despite the operation failing (the operation failure is recorded only in the audit log). Root cause is undocumented and the experiment confounded two variables at once.

No remotely-exploitable unauthenticated RCE was found by any report. No real secrets are committed. The security HIGHs are operator/config-reachable today and escalate to cross-tenant privilege issues under the multi-tenant API/runner model the codebase is explicitly building toward — which is why **the trust model for `odooctl.yml` is the single biggest severity multiplier and remains an open question to maintainers in all three reports.**

---

## 2. Current architecture / behavior understanding

### 2.1 Shape (from reports; consistent with this session's reads)

- **CLI-first** (`Typer`): `init`, `deploy`, `backup`, `restore`, `clone`, `update-modules`, `rollback`, `promote`, `logs`, plus sub-typers `env`, `project`, `ops`, `security`, `domain`, `dr`, `migrate`. **[SRC] `main.py:48-147`**
- **Optional control plane (M12/M13):** an **unprivileged** FastAPI app (read state, enqueue operations, stream SSE events, read audit) and a **privileged** runner (Docker/Postgres/git/tar). They are separate processes bridged by **HMAC capability tokens**. The documented boundary lives in `security/runner_contract.py` and `docs/plans/m11-security-architecture.md`.
- **Layering:** `adapters/` (docker-compose, postgres, filestore, S3, proxy) · `odoo/` (sanitize, db-swap, healthcheck, module-update) · `services/` (orchestration) · `commands/` (CLI) · `api/` + `runner/` (control plane) · `security/` (identity/RBAC/tokens/secrets/redaction) · `importer/` (adoption).
- **Execution modes:** `host` (config default) vs `docker`. The DB/filestore operations that contain the `sh -lc` sinks run in **docker** mode. **[EXEC]** Report 3 shows the test host had no `pg_dump`/`psql`, so docker mode is required there in practice.

### 2.2 Authorization spine (corroborated across reports)

`bearer token → get_principal → RBAC role map → enqueue → mint capability token (HMAC) → runner verifies (action/env/project scope) → consume nonce → env lock → privileged service call → append-only audit`. Positive controls observed by **multiple** reports and partly re-verified here:

- `serve` refuses to start without `--api-key`/`ODOOCTL_API_KEY`; binds `127.0.0.1` by default. (R2 positive controls; R3 ran it.)
- Capability tokens: HMAC-SHA256, expiry, constant-time compare, no alg-confusion, server-side role re-derivation, runner-side **single-use nonce** consumption. (R1 §6, R2 positive controls.)
- Protected-environment RBAC floor enforced at **both** API enqueue (`routes_operations.py:110`) and runner (`worker.py:155`) — the M12-blocked gap is remediated. (R1 §6/§7.)
- **[EXEC]** Report 3 drove the full chain end-to-end on disposable projects: mint operator token → `GET /projects`, `/environments`, `/status`, `/backups`, `/audit` → `POST /operations` (enqueue) → `runner --once` (process) → audit reflects outcome.

### 2.3 Runtime behavior actually observed (Report 3, [EXEC])

**Worked on both Odoo 18.0 and 19.0** (disposable docker-native stacks): `validate`, `doctor --json`, `status --json`, `logs --no-follow`, `backup production --verify`, `clone production staging --sanitize`, `update-modules staging`, `restore production --to staging --backup latest`, `import --preview`, `setup --yes`, `project add/list`, `serve`, `security token mint`, and all authenticated API read routes + enqueue + `runner --once`.

- The **`restore --to`** cross-environment path (the "safe" `restore_to_env` model Report 1 praised) ran and emitted `DROP DATABASE` then `ALTER DATABASE` — i.e. it restores into a `<db>_incoming` temp DB then **drops the target and renames** the temp in. This is the swap mechanism; it succeeded because no fault was injected.
- The **docker clone path** (which contains the `sh -lc` DB-clone sink) executed on the normal `clone --sanitize` path with benign identifiers — so the F1 sink is on a **default, exercised** code path in docker mode, not a dormant one.
- **Odoo version specifics:** 18.0 loads 12 base modules; 19.0 loads 14 including **`auth_passkey`** (a new WebAuthn/passkey authentication surface) and a heavier `html_editor`. Odoo 19 logs a warning that it **binds `0.0.0.0` by default** inside the container (changing to `127.0.0.1` in 20.0). Staging `ir_config_parameter` counts after sanitized clone: 18→10, 19→9 (sanitize ran without error; *contents* were not asserted).

---

## 3. Confirmed issues (test-observed [EXEC] or verified-in-source [SRC])

### C1 — `master` is RED: 14 failing tests, single root cause = global project-context not propagated **[EXEC]+[SRC]** — Release-blocker

- **[EXEC] Report 3 full suite: `14 failed, 709 passed`.** Failures: `tests/test_env_cmd.py` ×10 (list/show, create, destroy, open), `tests/test_promote.py` ×2 (`requires_yes_for_protected_target`, `yes_flag_bypasses_protection`), `tests/test_registry.py` ×2 (`global_project_option_resolves...`, `project_dir_option_resolves...`). Every failure shows the identical symptom: `Config file not found: /home/dev/odooctl/odooctl.yml`.
- **[EXEC] Report 2 reproduced the 2 promote failures in isolation** (`test_clone.py test_restore.py test_promote.py → 46 passed, 2 failed`) and diagnosed it with a minimal Typer-runner proof (`CONFIG_ARG=odooctl.yml`, `captured_config_exists=False` when invoked with `--project-dir <tmp>`). This is Report 2's **F6**.
- **[SRC] Root cause confirmed this session** at `main.py:54-63`: `_context_config()` recovers the global selection via `click.get_current_context(silent=True).find_root().obj`. The callback (`main.py:66-79`) stores `ctx.obj = {"project": ..., "project_dir": ...}`. Under Typer command wrappers / `CliRunner`, the root `ctx.obj` is not reliably reachable from inside `_context_config`, so `project`/`project_dir` resolve to `None`, the guard at `main.py:60` returns the bare default `config="odooctl.yml"`, and resolution falls back to cwd. Every destructive top-level command routes config through `_context_config` (`deploy:88`, `backup:96`, `restore:107/110`, `clone:122`, `update-modules:128`, `rollback:132`, `promote:143`, `logs:147`); `init` does not (consistent with it not failing). The `env` sub-typer shows the same symptom, so the sub-typers need the same fix.
- **Why this is the release-blocker, and why I elevate it above Report 2's "Medium":** it is the dominant cause of a red branch (blast radius = the entire CLI surface when `--project`/`--project-dir` is used), **and** it is a safety defect — for a destructive command, a user who believes they target project A can silently operate against the cwd. Severity elevation is a synthesized judgment from Report 3's blast-radius evidence + the destructive-targeting dimension, not an invented fact.

### C2 — API/runner-enqueued `backup staging` failed on both Odoo 18 and 19; `runner --once` masks it **[EXEC]; cause [HYP]**

- **[EXEC]** In both version runs, the audit log records `{"actor":"api-client","action":"backup","target":"staging","outcome":"failed"}` for the operation enqueued via `POST /operations` and processed by `runner --once`. Meanwhile every **CLI** operation (`backup production`, `clone`, `update-modules`, `restore`) recorded `succeeded`.
- **[EXEC]** `runner --once` **exited `0`** in both runs despite processing a failed operation. Report 3's own "What worked" section optimistically lists "staging queued backup via API/runner … where command logs show exit 0" — but its audit output contradicts that: the operation **failed**. The runner surfaces operation failure only in the audit/operation record, **not** in its process exit code. That is operationally dangerous for CI/cron/monitoring.
- **[HYP] Cause is undocumented and the experiment confounded two variables**: it changed *both* the execution path (CLI → API/runner) *and* the environment (`production` → `staging`) at once, and `staging` had just been mutated by a cross-env restore. The experiment never tested `backup staging` via CLI, nor `backup production` via API/runner, so the failure cannot be cleanly attributed to the queued/runner path vs. backing up the `staging` env vs. residual post-restore state. **Must be root-caused before claiming API/runner or Odoo 18/19 operational parity.**

### C3 — Three `sh -lc` injection sinks are present and on an exercised path **[SRC]+[EXEC reachability]** (= R1 F1 / R2 F1, HIGH)

- **[SRC]** Confirmed present this session: `adapters/db.py:124` (DB clone), `adapters/filestore.py:99` and `:113` (filestore wipe/copy). These are the *only* shell sinks in the package (both reports' repo-wide greps concur).
- The interpolated values (`src`/`dst` db names, filestore segment name, `internal_host`, `service_user`) originate from config / CLI with **no charset validation** — `validate_environment_graph` checks uniqueness/graph only. Report 2's capture-only proof showed injected shell markers survive into the `sh -lc` script (`db_clone_shell_marker_present=True`, `filestore_shell_marker_present=True`) and that a malicious config validates (`malicious_config_validation_succeeded=True`).
- **[EXEC]** Report 3 ran `clone production staging --sanitize` in docker mode → the DB-clone `sh -lc` path executed normally with benign identifiers. Combined with the host lacking `pg_dump`/`psql` (docker mode is the practical norm), this sink is a **default, live** path, not dormant.

### C4 — Literal `== "production"` guards instead of `is_protected()` **[SRC]** (= R1 F2 / R2 F2, HIGH)

- **[SRC]** Confirmed present this session: `services/deploy.py:72` (pre-deploy backup) and `:103` (failure restart), `services/clone.py:41` (unsanitized-prod-clone refusal), `odoo/db_swap.py:52` (swap-into-prod refusal), `config.py:173` (clone-target guard), `commands/env.py:286` (destroy refusal), **plus `commands/env.py:124`** (a *second* env guard, e.g. reserved-name on open/create, which Report 1 did **not** enumerate — this *widens* the finding). `config.py:237` is the legitimate `is_protected()` definition (not a bug); `services/branch.py:58` derives tier with the same literal and should be reviewed too.
- The policy `is_protected()` (`config.py:233-237`) covers `protected: true` **or** `tier == "production"` **or** `name == "production"`. So an env named `live`/`prod`/`prod-eu` with `tier: production` or `protected: true` is "protected" by policy yet bypasses every literal guard: **no pre-deploy backup, no clone-sanitize refusal, no db-swap guard, can be a clone target, can be `env destroy --purge`'d** — directly contradicting `README.md` ("Production deploys create … backups before deployment") and `SECURITY.md`/`docs/security.md` (clone-sanitize refusal). The newer `restore_to_env` path already uses `is_protected()` correctly, which makes the inconsistency more dangerous (operators assume uniform enforcement).

### C5 — `cancel` is gated by a READ action; VIEWER can cancel **[SRC]** (= R1 F6, was single-source; now verified)

- **[SRC]** Confirmed this session: `routes_operations.py:230-234` gates `cancel_operation` on `require_action(Action.OPERATIONS)`; `rbac.py:48-49` places `Action.OPERATIONS` in `READ_ACTIONS`; `rbac.py:68` grants `READ_ACTIONS` to `Role.VIEWER`. **A viewer token can cancel any queued operation** — a state-changing/DoS action behind a read permission. No `Action.CANCEL` exists (grep returned none). Report 1 F6 is accurate; the per-project/`org_id` scoping half of F6 (reads/cancels not scoped) remains [SOLO] static (plausible, not separately verified here).

---

## 4. Likely issues (static-analysis concerns; not runtime-demonstrated)

### L1 — Drop-before-verify with no rollback **[CONCUR]** (R1 F3+F4 / R2 F3, HIGH)

`run_restore` (`services/restore.py:136-152`) restores directly into the **live** DB; the docker adapter's `restore()` calls `drop_create()` (drop `--if-exists` + create) **before** `pg_restore`, so a corrupt/partial dump, disk-full, or killed process leaves the live DB gone with no rollback, and `run_restore` carries **no `is_protected` guard**. `swap_temp_database` (`odoo/db_swap.py:56-58`) runs `terminate_connections → drop_database → rename_database` as three non-transactional steps with a **no-target-DB window** (and `terminate_connections` doesn't set `datallowconn=false`, so a reconnect can break the drop/rename). Most acute: **promote's rollback** (`services/promote.py:153`) calls `run_restore` against the protected target, so a failed rollback can drop production and not restore it. And a **failed production deploy** (`deploy.py:101-108`) only `compose.restart`s — it **never restores the backup it just took** at `deploy.py:72-75`, which cannot undo a half-applied migration. **[EXEC] partial:** Report 3 showed the drop→rename swap executing successfully in `restore --to`; it did **not** inject a mid-window failure, so the irreversibility claim is consistent-but-not-demonstrated.

### L2 — DB password on argv leaks via unredacted `CommandError` → operation error → API **[CONCUR]** (R1 F5 / R2 F4, MEDIUM)

`odoo/module_update.py:24-28` appends `--db_password <value>` to argv. `CommandError` (`utils/shell.py:20-23`) joins `result.args` **without** redaction (`redact()` is applied only to stdout/stderr). The leak chain: clone/update-modules fails → runner `error_msg = str(exc)` → `store.update_status(..., error=error_msg)` → `GET /operations/{id}` returns `op.error` and SSE streams it → **an authenticated viewer can read the production DB password** from a failed operation. Report 2's canary proof: `argv_secret_leak_verified=True, argv_secret_arg_index=6`. Also visible to anyone who can `ps` in the container.

### L3 — Traefik `Host()` rule injection from unvalidated domain **[CONCUR]** (R1 F8 / R2 F5, MEDIUM)

`domains/traefik.py:34-40` builds `{"rule": f"Host(\`{spec.domain}\`)"}` from an unvalidated `domain` (`config.py:30` bare `str`); `services/domain.py` persists the raw value back to config. A crafted domain (backticks + a second matcher) broadens the route. YAML structure is safe (scalar via `yaml.dump`); the **rule grammar** is injectable. Report 2 proof: `traefik_rule_injection_marker_present=True`.

### L4 — Sanitization completeness gaps **[SOLO]+[EXEC context]** (R1 F7, MEDIUM)

Safe-by-default and correctly escaped, but incomplete (this is *coverage*, not injection): **`web.base.url.freeze` is never set** (so the base URL reverts to the live hostname on the next admin login, re-poisoning email/reset/OAuth/webhook links); only `payment_provider` is disabled (a **no-op on Odoo ≤15** where the table is `payment_acquirer` — real acquirers stay enabled); the **`minimal` profile strips the cron-disable** (scheduled invoice/bank/IAP/SMS/capture jobs run against real endpoints in the clone); OAuth providers / SMS-IAP / SMTP creds are not explicitly neutralized. **[EXEC] forward-looking:** Report 3 shows Odoo 19 ships **`auth_passkey`** — a new credential surface a sanitized staging clone will contain and that `sanitize.py` does not address. Report 3 confirms only that sanitize *runs* clean; it did **not** assert what was or wasn't neutralized, so it neither confirms nor refutes the specific gaps.

### L5 — Other single-source static concerns (R1 only) **[SOLO]**

Plausible and line-referenced by Report 1, not independently corroborated by Report 2/3:

- **Per-project/org scoping not enforced** on `get`/`stream`/`cancel` operations though `Principal` carries `org_id` (R1 F6 second half).
- **Secret master key co-located** with ciphertext under `secrets/` in the keyless-default mode (R1 F9).
- **Registry/config path escape** — an absolute `config` can point outside the project root; `odooctl -p evil` loads attacker-chosen config (R1 F10).
- **No confirmation** on `restore` / `rollback --mode full` while `promote`/`env destroy` require `--yes` (R1 F11).
- **LOW/observations (R1 F12–F24):** capability TTL 1h vs 300s default + unbounded nonce store + API reads not nonce-checked (F12); unkeyed audit hash, tail-truncation undetectable (F13); self-validating backup manifests + unconfined `resolve_backup_dir` (F14); healthcheck follows redirects, any 3xx = healthy (F15); short-secret/divergent-redactor gaps (F16); duplicated literal-escaping (F17); cron-line interpolation (F18); migration-report path traversal (F19); `import --output … --force` writes anywhere (F20); `runner_contract` misses transitive `services` imports + stale docstring (F21); docs drift — `token mint` example uses `ODOOCTL_RUNNER_KEY` while API verifies with `ODOOCTL_API_KEY`, `serve --host 0.0.0.0` example, "binds localhost" comment conflates Host-filtering with socket bind (F22); `-p` overloaded (global `--project` vs `serve --port`) and no `--dry-run` on the most destructive commands (F23); no key-strength floor on `ODOOCTL_API_KEY`/`ODOOCTL_RUNNER_KEY` (F24).

---

## 5. Failure points / risk concentrations

Ranked by blast radius × fix leverage. Note that the top two each have a **single root cause behind multiple symptoms** — fix the cause, retire several findings.

1. **CLI context-resolution layer** (`main.py:_context_config` + callback + sub-typers). *One* defect → 14 red tests **and** wrong-project targeting for destructive commands. Highest blast radius; reliability + safety. → **C1.**
2. **Config-boundary input validation** (`config.py` field validators absent). *One* missing validator layer is the root cause of **both** the `sh -lc` injection (C3) **and** the Traefik rule injection (L3). Single fix, two HIGH/MEDIUM findings. → **C3 + L3.**
3. **Environment-protection policy consistency** (`is_protected()` vs literal `"production"`). *One* inconsistency defeats the headline safety promise across deploy/clone/db-swap/destroy/clone-target/env-open. Six+ call sites, one semantic fix. → **C4.**
4. **Destructive DB lifecycle** (`adapters/db.py` + `odoo/db_swap.py` + `services/{restore,deploy,promote}.py`). Drop-before-verify, no rollback, no-DB windows, failed-deploy-doesn't-restore. The most *invasive* rework; concentrated data-loss risk. → **L1.**
5. **Secret handling at error edges** (`module_update.py` argv → `shell.py` CommandError → `worker.py` op.error → API/SSE). A single unredacted join exposes the DB password to authenticated viewers. → **L2.**
6. **API/runner control plane** — newest, least battle-tested; empirically a queued backup *failed* (C2), `runner --once` masks operation failure (C2), cancel is under-gated (C5), org scoping unenforced (L5). Concentrated where the product is heading (multi-tenant).
7. **Severity multiplier — trust model for `odooctl.yml`.** All three reports flag this as the swing factor: if project config (db_name/domain/filestore/internal_host) can be influenced by anyone less trusted than the runner operator (multi-tenant, self-service onboarding, imported third-party compose, PR-supplied config), then C3/L3 and the registry-escape (L5) jump from "operator foot-gun" to **runner privilege escalation across the very boundary `runner_contract.py` exists to protect.** This is an open question to maintainers, not a settled fact.

---

## 6. Next-step plan and recommended execution order

Precise enough to hand to implementation workers. Each task lists **files**, **change**, and an **acceptance gate**. Ordering rationale: P0 first because the branch is red and the context bug is also a safety bug — you cannot trust test-based verification of security fixes until green. Then the single-fix-multi-finding items (validators, policy unification) before the invasive lifecycle rework. P1c and P1d touch disjoint files and can run in parallel.

### P0 — Make the branch green & trustworthy (reliability + safety)

- **P0.1 — Fix global `--project`/`--project-dir` propagation (C1).**
  - Files: `main.py:54-79` (`_context_config` + callback) and the sub-typers `commands/{env,domain,project,ops,dr,migrate}.py`.
  - Change: stop relying on `click.get_current_context()` to recover the root `ctx.obj`. Thread the Typer context explicitly into each command (accept `typer.Context` and read `ctx.obj`, or resolve+store the selected config path once in the callback and have commands consume it), so `resolve_project_context(project, project_dir, config)` always receives the global selection.
  - Acceptance: the **14** named tests pass; add a regression **matrix** invoking every top-level command **and** every sub-typer command with `--project <registered>` and `--project-dir <dir>` from a *foreign* cwd; full `pytest -q` is green.

- **P0.2 — Root-cause the API/runner staging-backup failure and stop the runner from masking failures (C2).**
  - Files: `runner/worker.py`, `commands/runner.py`, `services/backup.py`, `api/queue.py`.
  - Change: reproduce in a disposable project (enqueue `backup` for a **non-production** env, then enqueue `backup` for **production** via API, and run `backup staging` via **CLI**) to disentangle the runner-path vs. staging-env vs. post-restore-state confound; fix the actual defect. Make `runner --once` return a **non-zero** exit (or an explicit machine-readable failure signal) when a processed operation ends `failed`.
  - Acceptance: queued non-production backup succeeds end-to-end; `runner --once` exit code reflects operation outcome; a regression test asserts a failed queued op yields non-zero runner exit.

### P1 — Security HIGH (both static reports concur; verified present in source)

- **P1.1 — Add config-boundary validators, then remove the shell sinks (C3 + L3).**
  - Files: `config.py` (field validators on `EnvironmentConfig.{db_name,filestore_path,filestore_volume,domain}`, `PostgresConfig.{internal_host,service_user}`, `OdooConfig.filestore_container_path`, `SanitizationConfig.temp_db_suffix`); `adapters/db.py:124`; `adapters/filestore.py:99,113`; `domains/traefik.py:34-40`.
  - Change: identifier validator `^[A-Za-z_][A-Za-z0-9_]{0,62}$` for DB identifiers; a safe path-segment validator for filestore names; an FQDN/IDNA hostname validator for `domain` (reject backticks/parens/whitespace/slashes/commas/logical-ops/schemes). Replace the three `sh -lc` strings with list-argument processes (pipe `pg_dump | pg_restore` in Python; separate `mkdir`/`rm`/`cp` `compose.exec` calls). Build the Traefik rule from the validated host only.
  - Acceptance: injection regression tests reject `;`, `$()`, backticks, space, newline in each field; `clone`/`restore`/`domain attach` still function; no `sh -lc` remains in `odooctl/` (grep gate in CI).

- **P1.2 — Unify protected-environment policy (C4).**
  - Files: `services/deploy.py:72,103`; `services/clone.py:41`; `odoo/db_swap.py:52`; `config.py:173`; `commands/env.py:124,286`; review `services/branch.py:58`. (Leave `config.py:237` — it is the definition.)
  - Change: replace every literal `== "production"` destructive guard with `cfg.is_protected(name)`; where helpers lack config access, pass a precomputed `target_is_protected` boolean.
  - Acceptance: regression test that a `tier: production` (and a `protected: true`) env **not named** `production` receives the pre-deploy backup, the unsanitized-clone refusal, the db-swap refusal, the clone-target rejection, and the destroy refusal — identically to one named `production`.

- **P1.3 — Verify-before-destroy + rollback for the destructive DB lifecycle (L1).**
  - Files: `services/restore.py` (`run_restore`), `odoo/db_swap.py:52-58`, `services/deploy.py:101-108`, `services/promote.py:153`.
  - Change: make `run_restore` restore into a temp DB and atomically swap (mirror `restore_to_env`) and add an `is_protected` policy; implement db-swap as **rename-old-aside → rename-temp-to-target → healthcheck → drop-old**, reverting on failure; set `ALLOW_CONNECTIONS false` before terminate/drop; on protected deploy failure **restore the `backup_id`** (or run module updates against a temp DB then swap) instead of only restarting.
  - Acceptance: a fault-injection test that fails `pg_restore` (or the healthcheck) mid-operation leaves the **live DB intact** and the env serviceable; promote-rollback failure does not destroy the protected target.

- **P1.4 — Keep the DB password off argv and redact error edges (L2). (Parallelizable with P1.3.)**
  - Files: `odoo/module_update.py:24-28`; `utils/shell.py:20-23`; `runner/worker.py` (persist/emit path).
  - Change: pass the DB password via an Odoo config file / container env / fd, not argv; run `CommandError`'s joined args through `redact()`; redact `error_msg` before persisting/streaming; feed resolved secret values into `security/redaction.redact(secret_values=…)` on API/runner error sinks.
  - Acceptance: a canary secret is absent from `str(CommandError(...))`, the persisted `operation.error`, and streamed SSE events.

### P2 — Security MEDIUM

- **P2.1 — RBAC: write-family cancel + scoping (C5 + L5).** Add `Action.CANCEL` (operator+) in `security/rbac.py`; gate `routes_operations.py:230-234` on it; scope `_find_op_ctx`/`get`/`stream`/`cancel` by `principal.org_id`/allowed projects and return **404** (not 403) for out-of-scope IDs. Acceptance: VIEWER cannot cancel; cross-org operation is invisible.
- **P2.2 — Sanitization completeness (L4).** Set `web.base.url.freeze='True'`; add a `payment_acquirer` companion statement (Odoo ≤15); keep cron-disable under `minimal` (or warn loudly); neutralize `auth_oauth_provider` and SMS/IAP; evaluate Odoo 19 `auth_passkey` credential neutralization; surface active toggles/profile in the clone preview.
- **P2.3 — Confirmations (L5/F11).** Require `--yes` (+ offer `--preview`) on `restore` and `rollback --mode full`, matching `promote`/`env destroy`.
- **P2.4 — Secret-store key (L5/F9).** Prefer `ODOOCTL_SECRET_KEY`/passphrase; warn in `doctor` when `master.key` is co-located with ciphertext.
- **P2.5 — Path containment (L5/F10,F14,F19,F20).** Reject/warn when a registry `config` resolves outside its `path` root; `resolve()` + assert the backup dir is under `backups_root`; HMAC-sign backup manifests; confine `import --output` and migration-report paths.

### P3 — Hardening (LOW + observations, R1 F12–F24)

Lower capability TTL toward 300s + TTL-purge the nonce store + nonce-check (or shorten) API read tokens; HMAC-key the audit chain with a sequence/count anchor against truncation; disable healthcheck redirect-following and require a 2xx (+ marker); unify the two redactors and token lists; add a key-strength floor for `ODOOCTL_API_KEY`/`ODOOCTL_RUNNER_KEY`; add `odooctl.services`/`runner`/`operations.engine` to `runner_contract` prefixes (or check transitively) and fix its stale docstring; refresh drifted docs (token-mint example → `ODOOCTL_API_KEY`, drop the `--host 0.0.0.0` example, fix the "binds localhost" comment); de-overload `-p`; add `--dry-run` to the destructive commands.

### Suggested sequencing at a glance

```
P0.1 ─┐ (green + safe baseline; do first)
P0.2 ─┘
        P1.1 (validators + de-shell)  ─┐  single-fix / multi-finding → early
        P1.2 (is_protected unify)     ─┘
        P1.3 (lifecycle rollback) ║ P1.4 (secret edges)   ← parallel, disjoint files
                P2.1..P2.5  →  P3
```

---

## 7. Contradictions / uncertainty

1. **Test posture: implied-green vs. empirically-red (resolved in favor of the experiment).** Report 1 asserts a "strong test posture," "~520 tests" (a project-memory estimate), and reads as green. **Report 3 [EXEC] shows 14 failed / 709 passed (723 total).** Per the task's precedence rule, the experimental evidence wins: **the branch is red; the real test count is ~723, not ~520.** Report 1's gap is methodological — it did not run the suite. **Not a factual conflict between equally-grounded claims; a static estimate corrected by execution.**

2. **F6 (project-context bug) severity: Report 2 "Medium" vs. this synthesis "release-blocker."** Report 2 framed it as "at least the top-level `promote` wrapper." Report 3 shows it is the root cause of **all 14** failures (env family + promote + registry). I elevate it on blast-radius + the destructive-targeting safety dimension. This is a *severity* divergence (a synthesized judgment), not a *factual* one — both reports agree the bug is real and [SRC]-confirmed here.

3. **F1 `sh -lc` reachability: "host-mode default, so off by default" (R1) vs. "docker mode is the practical norm" (R3).** Report 1 tempered F1 by noting the config default is `host`. **Report 3 [EXEC] shows the host lacked `pg_dump`/`psql`, so docker mode is required there** and the DB-clone `sh -lc` path executes on the normal `clone` flow. Both statements are individually true; the experiment **raises** the real-world reachability above Report 1's caveat. Prefer the experimental signal: treat the docker-mode sink as a **live default path**, not an edge case.

4. **Report 3's internal tension on the queued backup.** Its "What worked" lists the API/runner staging backup as exercised "where command logs show exit 0," but its audit output records that operation as `failed`. The reconciliation: **`runner --once` exited 0 while the operation failed** — exit code ≠ operation outcome. Treat "exit 0" from the runner as **not** a success signal. (See C2.)

5. **Coverage difference ≠ disagreement.** Report 2 surfaced only 6 findings and explicitly scope-limited after its breadth sub-scan timed out; it is **silent** on R1's F6-scoping, F7 sanitization, F9–F24. Silence is *not* refutation. Where Report 2 is silent, those items rest on Report 1's single-source static analysis ([SOLO]) — I verified the cancel-by-read half of F6 ([SRC]) and left the rest labeled [SOLO].

6. **Genuinely unresolved (uncertainty, not contradiction):**
   - **Root cause of the C2 queued-backup failure** — unknown; confounded experiment.
   - **Whether the 10 `test_env_cmd` failures share C1's exact root cause** — they share the identical `Config file not found` symptom and were only observed in the full-suite run (the 4 promote/registry failures were the ones reproduced/diagnosed in isolation). High likelihood same cause; not independently isolated for the env family.
   - **The `odooctl.yml` trust boundary** — the dominant severity multiplier for C3/L3/L5; an open question in all three reports.
   - **L1 irreversibility at runtime** — the drop→rename mechanism was observed succeeding; no mid-window failure was injected, so the data-loss claim remains static.

---

## 8. Explicit confidence notes

- **HIGH — branch is red (14 failures) and C1 is the root cause for the promote+registry subset.** Executed full suite (R3) + isolated reproduction & diagnosis (R2) + [SRC] root-cause confirmation this session.
- **HIGH-but-not-isolated — C1 also causes the 10 `test_env_cmd` failures.** Identical symptom, full-run-only observation.
- **HIGH (in source), not exploit-demonstrated — C3 (`sh -lc`), C4 (literal `production`), C5 (cancel-by-read).** Two independent static reviews concur (C3/C4) and/or [SRC]-verified here (C3/C4/C5); no live exploit/PoC was run against a deployed instance, so these are "confirmed in code," not "demonstrated end-to-end."
- **HIGH on occurrence / LOW on cause — C2 (queued staging backup failed; runner masks it).** The failure and the exit-0 masking are directly visible in R3 output; the cause is unexplained and confounded.
- **MEDIUM-HIGH — L1, L2, L3.** Both static reports concur with line references and (for L2/L3) Report 2 proof scripts; runtime not exercised for the failure paths.
- **MEDIUM — L4, L5 single-source items.** Report 1 only; plausible and line-referenced; uncorroborated by R2/R3. (Cancel-by-read was the exception and is now [SRC].)
- **MEDIUM-HIGH — Odoo 18/19 happy-path parity.** Both versions ran the core CLI + API/runner flows end-to-end; but coverage was not exhaustive, one queued op failed (C2), and the destructive *failure/rollback* paths (L1) were never fault-injected. Odoo 19's `auth_passkey` and default `0.0.0.0` in-container bind are confirmed observations.
- **CONDITIONAL — multi-tenant severity.** All HIGH security items escalate under a less-trusted-config model; the trust boundary is an open question, so escalation is conditional, not asserted.

---

### Appendix — Unified finding map

| U# | Title | R1 | R2 | R3 [EXEC] | Evidence here | Severity (synth) |
|----|-------|----|----|-----------|---------------|------------------|
| **C1** | Global `--project`/`--project-dir` ignored → 14 red tests; wrong-project targeting | (F23 notes `-p` overload only) | **F6** | **14 fail / 723** | [EXEC]+[SRC] | **Release-blocker** |
| **C2** | API/runner `backup staging` failed (18 & 19); `runner --once` exits 0 on failure | — | — | **failed ×2** | [EXEC]; cause [HYP] | **High (investigate)** |
| **C3** | `sh -lc` injection from unvalidated db/filestore ids | F1 | F1 | clone sink executed (benign) | [CONCUR]+[SRC]+[EXEC reach] | High |
| **C4** | Literal `== "production"` vs `is_protected()` | F2 | F2 | not exercised on protected-non-prod | [CONCUR]+[SRC] (+`env.py:124`) | High |
| **C5** | `cancel` gated by READ action (VIEWER can cancel) | F6 | — | not exercised | [SRC] | Medium |
| **L1** | Drop-before-verify, no rollback (restore/db-swap/deploy) | F3+F4 | F3 | swap ran; no fault injected | [CONCUR]+[EXEC partial] | High |
| **L2** | DB password on argv → CommandError → API | F5 | F4 | not exercised | [CONCUR] | Medium |
| **L3** | Traefik `Host()` rule injection | F8 | F5 | domain benign | [CONCUR] | Medium |
| **L4** | Sanitization completeness (freeze/acquirer/cron/oauth/sms/passkey) | F7 | — | sanitize ran; contents unchecked; 19 has `auth_passkey` | [SOLO]+[EXEC ctx] | Medium |
| **L5** | org-scoping, secret-key co-location, registry escape, confirmations, F12–F24 | F6/F9/F10/F11/F12–F24 | — | — | [SOLO] | Med/Low/Obs |

*End of synthesis. Report-derived conclusions are tagged [CONCUR]/[SOLO]; direct source/execution verification performed in this synthesis is tagged [SRC]/[EXEC] against commit `659fad9`. No product code modified; no deployment/Docker/DB/network commands run.*
