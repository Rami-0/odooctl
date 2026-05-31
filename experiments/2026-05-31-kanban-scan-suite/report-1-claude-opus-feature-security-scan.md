# odooctl — Independent Feature & Security Audit

**Author:** Claude Opus 4.8 (automated audit agent)
**Date:** 2026-05-31
**Repository:** `/home/dev/odooctl`
**Branch inspected:** `master`
**Commit inspected:** `9e39a95dd3710b232e803305e0ba292589055b4b` (`docs: finalize odooctl progress push status`)
**Working tree:** clean at audit start
**Scope of product code:** 107 Python modules, ~9,884 LOC under `odooctl/` (excludes `.venv`); 46 test modules under `tests/`.

> This is an audit/report only. No product code was modified. Findings were verified by reading the
> actual repository; the most serious items were confirmed by direct file reads (line references below),
> with breadth coverage gathered by sub-agents and then spot-checked.

---

## 1. Commands & tooling used

Investigation was performed read-only inside `/home/dev/odooctl`:

- `git rev-parse HEAD`, `git branch --show-current`, `git log --oneline -5`, `git status --short` — pin branch/commit/state.
- `git ls-files | grep …` — enumerate tracked files; check for committed state/secrets under `.odooctl/`, `examples/`, `backups/`, `filestore/`.
- `find odooctl -name '*.py'` / LOC counts — map the package layout.
- `grep -rnE "shell\s*=\s*True|os\.system|os\.popen|eval\(|exec\(|pickle\.|yaml\.load\(|subprocess\.…"` over `odooctl/` — locate dangerous primitives.
- `grep -rnE "\"sh\"|sh -lc|bash -c"` and an f-string-into-SQL/command heuristic — locate shell-string construction sinks.
- `grep -niE "(password|secret|api_key|token)\s*[:=]\s*…"` over tracked docs/examples — check for inline secrets (all matches were placeholders/env references).
- Direct `Read` of the security-critical modules: `utils/shell.py`, the whole `security/` package (`rbac`, `tokens`, `principals`, `secrets`, `redaction`, `runner_contract`), the `api/` package (`app`, `auth`, `routes_operations`, `queue`), `runner/worker.py`, `adapters/db.py`, `adapters/filestore.py`, `config.py`, `services/clone.py`, `services/deploy.py`, `services/restore.py`, `odoo/module_update.py`, `operations/audit.py`, `commands/serve.py`, `commands/runner.py`, `commands/env.py`.
- Four parallel sub-agents performed breadth coverage of the adapters, services, sanitize/db-swap/migration, importer/catalog/domains, and docs-vs-implementation drift; their candidate findings were re-verified against source before inclusion.

---

## 2. Methodology

1. **Map the trust model.** odooctl is a CLI-first Odoo deployment tool with an *optional* HTTP control plane (M12 FastAPI API + durable queue + privileged runner) and a static web UI (M13). The documented security boundary (`docs/plans/m11-security-architecture.md`, `security/runner_contract.py`) is: the **API/web process is unprivileged** (read state, enqueue, stream events, read audit) and the **runner is privileged** (Docker/Postgres/git/tar). Capability tokens (HMAC) bridge the two.
2. **Follow the data to the dangerous sinks.** Trace operator/config/CLI/API input into the three sink classes that matter for this tool: OS commands (`subprocess`/`docker compose exec`), SQL (`psql -c`), and filesystem destruction (`drop database`, `rmtree`, filestore replace).
3. **Check the authorization spine end-to-end:** bearer token → `get_principal` → RBAC → enqueue → capability token → runner verify → nonce → lock → service call → audit.
4. **Audit the deployment-sensitive flows** (backup, restore, clone, promote, rollback, DR, env destroy) for protection of production, atomicity, and rollback-on-failure.
5. **Compare documentation claims to enforced behavior.**
6. **Calibrate severity to the documented threat model** (single host, trusted operator, `SECURITY.md` excludes "attacker already has shell/Docker-socket access"), while flagging where the *roadmap toward multi-tenant/API operation* changes that calculus.

---

## 3. Executive summary

odooctl is a **well-engineered codebase with a security-aware design**: list-argument subprocess calls (no `shell=True` almost everywhere), HMAC capability tokens with constant-time comparison and no algorithm-confusion, an encrypt-then-MAC stdlib secret store with `0600` files, `yaml.safe_load` throughout, a side-effect-free importer that refuses to inline literal passwords, a flock-guarded hash-chained audit log, and — notably — the M12-blocked "protected-environment RBAC floor" is now **enforced at both the API enqueue layer and defensively re-checked in the runner**.

The findings cluster into **four systemic themes**:

1. **Shell-string construction from unvalidated identifiers.** Three `sh -lc` sites interpolate db/filestore names directly into a shell; the root cause is that `db_name`, `filestore_path`, `temp_db_suffix`, and `domain` are plain `str` with **no charset validation** anywhere in the config model. (Finding F1, F8)
2. **`== "production"` literal checks instead of `is_protected()`.** The config defines a rich `is_protected()` (covers `protected: true` and `tier: production`), but at least six destructive guards still compare to the literal string `"production"`. Any protected environment *not literally named* `production` silently loses pre-deploy backups, the clone-without-sanitize refusal, and the db-swap guard. This directly contradicts the README's headline safety promise. (Finding F2)
3. **Destructive operations that drop-before-verify with no rollback.** `run_restore` and `swap_temp_database` destroy the live database before the replacement is verified; a production deploy that fails after the module-update phase is "recovered" only by a container restart, never by restoring the backup it just took. (Finding F3, F4)
4. **Secret/authorization leakage at the edges.** The Odoo DB password is passed on `--db_password` argv and leaks through the unredacted `CommandError` args into operation-error fields exposed by the API; `cancel_operation` (a mutation) is gated by a *read-only* RBAC action; and reads/cancels are not scoped per project/org. (Finding F5, F6)

No remotely exploitable, unauthenticated RCE was found. No real secrets are committed. The HIGH items are reachable by an operator/config and become substantially more serious under the multi-tenant API/runner model the architecture is explicitly building toward.

### Findings at a glance

| ID | Severity | Title | Primary location |
|----|----------|-------|------------------|
| **F1** | **High** | OS command injection via `sh -lc` f-strings (unvalidated db/filestore identifiers) | `adapters/db.py:123`, `adapters/filestore.py:99,113` |
| **F2** | **High** | Destructive guards use literal `== "production"` instead of `is_protected()` | `services/deploy.py:72,103`; `services/clone.py:41`; `odoo/db_swap.py:52`; `config.py:173`; `commands/env.py:286` |
| **F3** | **High** | Drop-before-verify with no rollback in restore / db-swap (no-DB window, data-loss) | `services/restore.py:136-152`; `odoo/db_swap.py:56-58`; `services/promote.py:153` |
| **F4** | **High** | Failed production deploy never restores its backup (only restarts container) | `services/deploy.py:101-108` |
| **F5** | **Medium** | DB password on `--db_password` argv leaks via unredacted `CommandError` → operation error → API | `odoo/module_update.py:28`; `utils/shell.py:22`; `runner/worker.py:193,206` |
| **F6** | **Medium** | `cancel` gated by read-only action; cross-project/org reads not scoped | `api/routes_operations.py:230-235,63-80` |
| **F7** | **Medium** | Sanitization completeness gaps (base-url freeze, payment_acquirer, minimal-profile crons, OAuth/SMS) | `odoo/sanitize.py:31-32,61-64,72-73` |
| **F8** | **Medium** | Traefik `Host()` rule built by unescaped f-string → routing-rule injection | `domains/traefik.py:35` |
| **F9** | **Medium** | Secret-store master key co-located with ciphertext; default keyless local key | `security/secrets.py:368-373` |
| **F10** | **Medium** | Registry/config paths unconstrained; absolute config can escape project root | `registry.py:45-49,76-77`; `context.py:28-39` |
| **F11** | **Medium** | `restore` and `rollback --mode full` run destructively with no confirmation | `main.py:99-132`; `services/restore.py`; `services/rollback.py` |
| **F12** | **Low** | API capability-token TTL 1h + unbounded nonce store; API read tokens not nonce-checked | `api/routes_operations.py:141`; `runner/worker.py:63-91` |
| **F13** | **Low** | Audit chain is unkeyed SHA-256; tail-truncation undetectable | `operations/audit.py:12-15,62-72` |
| **F14** | **Low** | Backup manifest self-validating (no signature); `resolve_backup_dir` not confined to backups root | `services/restore.py:31-33,40-70` |
| **F15** | **Low** | Healthcheck follows redirects; any 3xx counts as "healthy" (SSRF-adjacent, false pass) | `odoo/healthcheck.py:24,28` |
| **F16** | **Low** | Short secrets (<6) never redacted; two divergent redactors; broad ignore list | `utils/shell.py:9-11,38`; `security/redaction.py:26` |
| **F17** | **Low** | Inline literal-escaping duplicated instead of shared helper | `adapters/db.py:94` |
| **F18** | **Low** | Schedule generator interpolates `--interval`/`--user`/paths unquoted into cron lines | `commands/schedule.py:82-96` |
| **F19** | **Low** | Migration report filename derived from unsanitized env/version (path traversal) | `migration/rehearse.py:223-228` |
| **F20** | **Low** | `import --output … --force` writes anywhere; no root containment | `importer/adopt.py:26-31` |
| **F21** | **Obs.** | Runner contract misses transitive privileged imports via `odooctl.services`; stale docstring | `security/runner_contract.py:33-36` |
| **F22** | **Obs.** | Docs drift: token-mint examples, key-env default, "binds localhost", `--host 0.0.0.0` example | `docs/api.md`, `docs/web-ui.md`, `commands/security.py:39` |
| **F23** | **Obs.** | `-p` overloaded (global `--project` vs `serve --port`); no `--dry-run` on the most destructive commands | `main.py:70,270` |
| **F24** | **Obs.** | No key-strength floor for `ODOOCTL_API_KEY` / `ODOOCTL_RUNNER_KEY` | `commands/serve.py:38-43`; `commands/runner.py:14-18` |

---

## 4. Prioritized findings (detail)

### F1 — HIGH — OS command injection via `sh -lc` f-strings built from unvalidated identifiers

**Affected:**
- `odooctl/adapters/db.py:121-124` — `DockerPostgresAdapter.clone_db_in_container`
- `odooctl/adapters/filestore.py:94-115` — `DockerVolumeFilestore.restore_archive` / `copy`
- Root cause: `odooctl/config.py:32` (`db_name: str`), `:33` (`filestore_path: str`), `:34` (`filestore_volume`), `:124` (`temp_db_suffix`), `:30` (`domain`) — none has a charset validator; `validate_environment_graph` (config.py:158-231) only checks uniqueness/graph.

**Evidence (verified by direct read):**

```python
# adapters/db.py:121
def clone_db_in_container(self, src: str, dst: str) -> None:
    self.drop_create(dst)
    script = f"pg_dump -Fc -h {self.config.internal_host} -U {self.config.service_user} -d {src} | pg_restore -h {self.config.internal_host} -U {self.config.service_user} -d {dst}"
    run(self._cmd("sh", "-lc", script), cwd=self.project_dir, env=self._password_env(), stream=True)
```

```python
# adapters/filestore.py:108
def copy(self, source: str, target: str) -> None:
    src = self._container_filestore_dir(source)
    dst = self._container_filestore_dir(target)
    self.compose.exec(self.service,
        ["sh", "-lc", f"mkdir -p {self.root}/filestore && rm -rf {dst} && cp -a {src} {dst}"], stream=True)
```

`src`/`dst` are database names; `dst`/`src`/`name` in filestore derive from `Path(filestore_path).name`. These values originate from config and from the `env clone` / `env open` CLI `--db-name` / `--filestore-path` options, with **no validation**. A value such as `x; touch /tmp/pwned` or `$(...)`/backtick payload executes arbitrary commands **inside the Postgres/Odoo container** under the service account.

**Reachability & severity rationale:**
- `clone_db_in_container` runs only in `execution_mode: docker` (default is `host`, `config.py:21`), reached via `services/clone.py:73-74`.
- The filestore `sh -lc` runs only when `filestore_volume` is set (`adapters/filestore.py:122-124`), reached via `services/clone.py:85`. `Path(...).name` strips `/` (so path traversal collapses) but **does not strip shell metacharacters** (`;`, `|`, `$()`, backticks, spaces, newlines), so it is still injectable, just constrained to a single path segment.
- Under the documented single-operator threat model this is operator-on-themselves (the injected command runs in the *container*, which is still a boundary crossing). **Under the multi-tenant API/runner model the codebase is building toward, db/filestore names live in per-project config that a lower-trust tenant controls, and the *privileged runner* executes the injection** — a privilege escalation across the very boundary `runner_contract.py` exists to protect. Rated **High**; treat as **Critical** if project config / db names can come from any source less trusted than the runner operator.

**Note:** Every other adapter call in the codebase correctly uses list-argument `run(...)`/`compose.exec(...)` with no shell — these three `sh -lc` strings are the only shell sinks (confirmed by repo-wide grep).

**Remediation:**
1. Add one identifier validator (e.g. `^[A-Za-z_][A-Za-z0-9_]{0,62}$`) as a `field_validator` on `EnvironmentConfig.db_name`/`filestore_path`/`filestore_volume` and on `SanitizationConfig.temp_db_suffix`. Defense-in-depth that closes F1 at the source.
2. Eliminate the shell strings: pipe `pg_dump | pg_restore` as two list-argument processes in Python; run `mkdir`/`rm`/`cp` as separate list-argument `compose.exec` calls.

---

### F2 — HIGH — Destructive guards check the literal string `"production"`, not `is_protected()`

**Affected (all verified):**
- `services/deploy.py:72` — pre-deploy backup only `if environment == "production"`.
- `services/deploy.py:103` — failure-recovery restart only `if environment == "production"`.
- `services/clone.py:41` — `if source == "production" and not should_sanitize:` (refuse unsanitized prod clone).
- `odoo/db_swap.py:52` — `if target_env_name == "production":` (refuse swap into prod).
- `config.py:173` — `if name == "production" and env.clone_from:` (config-time clone-target guard).
- `commands/env.py:286` — `if name == "production":` (refuse env destroy).

**The contradiction:** `config.py:233-237` defines protection broadly:

```python
def is_protected(self, name: str) -> bool:
    env = self.env(name)
    if env.protected is not None:
        return env.protected
    return name == "production" or env.tier == "production"
```

So an environment with `protected: true` or `tier: production` but **named `live`, `prod`, or `prod-eu`** is "protected" by policy yet bypasses every literal-string guard above. Consequences for such an env:
- **No pre-deploy DB/filestore backup** (`deploy.py:72`) — directly contradicts `README.md:65` "Production deploys create database and filestore backups before deployment."
- **No refusal when cloning it unsanitized** (`clone.py:41`) — real PII/credentials leak into staging. (`SECURITY.md` and `docs/security.md` promise this refusal.)
- **No db-swap protection** (`db_swap.py:52`) and **config validation won't stop it being a clone target** (`config.py:173`) — its live DB can be dropped/recreated without a backup.
- **Can be purged** via `env destroy --purge` (`env.py:286,313-314`: `db.drop()` + `fs.delete()` with no backup).

The newer code paths get this right — `services/restore.py:91-104` correctly uses `is_protected()` for both target-refusal and source-sanitization — which makes the inconsistency the more dangerous (operators reasonably assume uniform enforcement).

**Remediation:** Replace every literal `== "production"` destructive guard with `cfg.is_protected(<env>)`. This single change closes the deploy-backup gap, the clone-sanitize bypass, the db-swap bypass, the clone-target bypass, and the destroy bypass. Add a regression test that a `tier: production` env not named "production" is refused/backed-up identically.

---

### F3 — HIGH — Drop-before-verify with no rollback (no-DB window, irreversible loss on failure)

**Affected:**
- `services/restore.py:136-152` (`run_restore`) → `adapters/db.py:76-85` / `:93-106` (`restore` → `drop_create`).
- `odoo/db_swap.py:56-58` (`swap_temp_database`).
- `services/promote.py:153` (promote's own rollback calls `run_restore` against the protected target).

**Evidence:** `run_restore` calls `pg.restore(env.db_name, …)` directly on the **live** database; the adapter's `restore()` calls `drop_create()` first (`dropdb --if-exists` then `createdb`), i.e. it **drops the live DB before `pg_restore` runs**. If `pg_restore` then fails (corrupt/partial dump, disk full, killed process), the live database is already gone with no rollback. `run_restore` also has **no `is_protected` guard**, so it can target production directly.

`swap_temp_database` (`db_swap.py:56-58`) likewise runs `terminate_connections` → `drop_database(target)` → `rename_database(temp → target)` as **three separate `psql` invocations** (DDL on databases cannot be transactional). Between the drop and the rename there is a window with **no target database**; a crash or a re-opened connection causing the rename to fail leaves the environment with the old DB destroyed and the new one not in place, unrecoverable from within the function. `terminate_connections` kills current sessions but does not set `datallowconn=false`, so a client can reconnect and break the drop/rename.

The most acute instance: **promote's rollback path** (`promote.py:153`) uses `run_restore` on the protected target, so a failed rollback can drop production's DB and fail to restore it (the code does flag `rollback_ok=False` / "manual intervention required", but the live DB is already destroyed).

**Remediation:** Make `run_restore` restore into a temp DB and atomically swap (the pattern `restore_to_env` already implements at `restore.py:110-125`), and add an `is_protected` policy. In `swap_temp_database`, rename the old target aside (`ALTER DATABASE target RENAME TO target_old_<ts>`), health-check `temp_db`, then promote and only then drop the aside copy; revert on failure. Set `ALLOW_CONNECTIONS false` before terminate+drop.

---

### F4 — HIGH — A failed production deploy never restores the backup it took

**Affected:** `services/deploy.py:71-108` (verified by direct read).

```python
if environment == "production":
    backup_result = backup_execute(ctx, environment)   # backup taken (line 74)
    backup_id = backup_result.backup_id
...
update_modules_compose(compose, ...)                   # mutates live DB schema (82-91)
check_url(url, ...)                                    # healthcheck (93-98)
except Exception as exc:
    message = str(exc)
    if environment == "production":
        compose.restart(cfg.odoo.service)              # ONLY a restart (103-105)
    raise
```

A backup is created before a production deploy, but the failure path **never uses it**. `update_modules_compose` runs Odoo module upgrades against the live DB; if a migration half-applies and the healthcheck then fails, recovery is only `compose.restart` — which cannot undo a partially-applied schema/data migration. The freshly-created `backup_id` is only written into deployment metadata (`deploy.py:110-123`), never restored. This contradicts the safety expectation set by taking the backup. (Compounded by F2: a protected non-"production" env takes no backup at all.)

**Remediation:** On production deploy failure, restore the `backup_id` taken at line 74 (or run the module update against a restore-into-temp + swap), instead of only restarting the container. Gate on `is_protected`, not the literal name.

---

### F5 — MEDIUM — DB password placed on argv leaks via unredacted `CommandError` into API-exposed operation errors

**Affected:** `odoo/module_update.py:24-28`; `utils/shell.py:20-23`; `runner/worker.py:192-206`.

```python
# odoo/module_update.py:24
if db_password_env:
    value = os.getenv(db_password_env)
    ...
    args.extend(["--db_password", value])              # password on argv
```
```python
# utils/shell.py:20
class CommandError(RuntimeError):
    def __init__(self, result: CommandResult):
        super().__init__(f"Command failed ({result.returncode}): {' '.join(result.args)}\n{result.stderr}")
```

`shell.py`'s `redact()` is applied to captured `stdout`/`stderr`, but **`CommandError` joins `result.args` unredacted**. The Odoo DB password is in those args. The leak chain is concrete: `services/clone.py:90` calls `update_modules_compose`; if the module update fails, the runner does `error_msg = str(exc)` (`worker.py:193`) and `store.update_status(..., error=error_msg)` (`:206`); the API then returns `op.error` from `GET /operations/{id}` (`routes_operations.py:186`) and streams it via SSE. So an **authenticated viewer can read the production DB password** out of a failed clone's error. The password is additionally visible to anyone who can `ps` inside the Odoo container.

**Remediation:** Pass the DB password to Odoo via a config file or container env, not argv. Redact `CommandError`'s args (run the joined args through `redact()`), and redact `error_msg` before persisting/emitting it. Consider feeding resolved secret values into `security/redaction.redact(secret_values=…)` on the API/runner error paths.

---

### F6 — MEDIUM — `cancel` is gated by a read-only RBAC action; reads/cancels are not scoped per project or org

**Affected:** `api/routes_operations.py:230-235` and `:63-80`, `:168-187`, `:190-227` (verified).

`cancel_operation` depends on `require_action(Action.OPERATIONS)`. `Action.OPERATIONS` is in `READ_ACTIONS` (`rbac.py:48-50`), which `Role.VIEWER` holds. So a **viewer can cancel any queued operation** — a mutating/denial-of-service action gated only by a read permission. Cancelling a queued backup/deploy is a state change that should require at least operator.

Separately, `_find_op_ctx` (`:63-80`) iterates **all registered projects** to resolve an operation by ID, and none of `get_operation`/`stream_events`/`cancel_operation` scope to the caller's project or `org_id`. `Principal` carries `org_id` (`principals.py:87`) but it is never enforced. For the current single-tenant localhost deployment this is acceptable, but the model is explicitly built for multi-tenant ("principals always carry an org id so multi-tenant scoping can be added", `principals.py:60-62`), and as written any authenticated principal can read/cancel operations belonging to every project on the host.

**Remediation:** Introduce a write-family `Action.CANCEL` (operator+) for cancellation. When multi-tenant is enabled, filter `_find_op_ctx` by `principal.org_id`/allowed projects and return 404 (not 403) for out-of-scope IDs to avoid existence oracles.

---

### F7 — MEDIUM — Sanitization completeness gaps

**Affected:** `odoo/sanitize.py` (verified). Defaults are safe-by-default (all `SanitizationConfig` toggles default `True`, `config.py:117-123`), and the SQL is correctly single-quote-escaped, so this is about *coverage*, not injection:

- **`web.base.url.freeze` is never set** (`sanitize.py:61-64` writes only `web.base.url`). In Odoo, if the freeze flag is not `True`, the base URL is **rewritten back to the live hostname on the next admin web login**, silently reverting the staging URL to production and re-poisoning outbound email links, password-reset links, OAuth redirects, and webhook bases.
- **Only `payment_provider` is disabled** (`sanitize.py:31-32`). That table is `payment_acquirer` on **Odoo ≤15**; the `to_regclass('public.payment_provider')` guard makes the statement a **silent no-op** there, leaving real payment acquirers enabled — a staging clone on Odoo 14/15 can process real payments.
- **The `minimal` profile strips the cron-disable statement** (`sanitize.py:72-73`: `stmts = [sql for sql in stmts if "ir_cron" not in sql]`). Scheduled actions then run in the clone — invoice auto-send, bank sync, IAP/SMS, payment captures — against real endpoints.
- **OAuth providers (`auth_oauth_provider`), outgoing SMS/IAP, and SMTP credentials are not explicitly neutralized.** The strict-profile `auth_%` wipe touches `ir_config_parameter`, not the `auth_oauth_provider` table.

**Remediation:** Also set `web.base.url.freeze='True'`; add a `payment_acquirer` companion statement; keep cron-disable even under `minimal` (or warn loudly); add `auth_oauth_provider`/`sms_sms` disables. Surface the active toggles/profile in the clone preview so operators see what was *not* sanitized.

---

### F8 — MEDIUM — Traefik routing rule built by unescaped f-string (rule injection)

**Affected:** `domains/traefik.py:35` (verified by sub-agent, code quoted):

```python
router = {"rule": f"Host(`{spec.domain}`)", "service": service_name, ...}
```

`spec.domain` comes from `env.domain` / the `domain attach` CLI argument and has **no hostname validation** (`config.py:30` is a bare `str`). A crafted value like `` example.com`) || PathPrefix(`/ `` yields `Host(`example.com`) || PathPrefix(`/`)`, a logically broader matcher (classic Traefik rule injection) that can route arbitrary paths/hosts to the backend. YAML structure is safe (emitted as a scalar via `yaml.dump`), but the **rule-expression grammar** is injectable. `services/domain.py:50-52` then persists the unvalidated domain back into config so it re-applies on every deploy.

**Remediation:** Validate `domain` against a hostname regex at config load (reject backticks/parentheses/spaces); construct the matcher from a validated host only.

---

### F9 — MEDIUM — Secret-store encryption key co-located with the ciphertext; default keyless local key

**Affected:** `security/secrets.py:344-373` (verified).

The store itself is well-built (encrypt-then-MAC, random 16-byte nonce per encryption, `0600` files via `O_CREAT|fchmod`, `SecretValue` wrapper). The weakness is **key management**: when no passphrase and no `ODOOCTL_SECRET_KEY` are provided, `resolve_key` generates a random master key and persists it at `secrets/master.key` **right next to** the encrypted `secrets/secrets.json`. An attacker who can read the state directory (or a captured backup of it) obtains **both** the key and the ciphertext, so at-rest encryption provides essentially no protection against that threat — while presenting the appearance of protection. The `0600` mode helps only against *other* local users, not against the same user, a state-dir backup, or a compromised process.

**Remediation:** Prefer `ODOOCTL_SECRET_KEY` / passphrase (already supported) and document that the keyless mode is convenience-only. Consider deriving the key from an OS keyring or refusing to fall back to a co-located keyfile for production state. At minimum, warn (in `doctor`) when the master key is co-located.

---

### F10 — MEDIUM — Registry/config paths are unconstrained (confused-deputy)

**Affected:** `registry.py:45-49,76-77,109-125`; `context.py:26-39` (verified by sub-agent).

A registry entry's `path`/`config` may point anywhere on disk; `add_project` explicitly permits an **absolute `config` path that escapes the project `root`** (`registry.py:76-77`), and `resolve_project_context` will load it. An attacker who can append one line to `~/.config/odooctl/config.toml` (or ship a malicious project directory) makes `odooctl -p evil <cmd>` load and act on an attacker-chosen config — which drives the compose file, db names, domains, and the F1/F2/F3 sinks. This is a local/confused-deputy concern (requires write to the registry or a planted project), not remote RCE, and there is **no root containment or warning**. (Mitigations present: malformed entries are skipped, and TOML writing is escaped.)

**Remediation:** Reject or warn when a registry `config` resolves outside its `path` root; optionally maintain an allow-list of project roots.

---

### F11 — MEDIUM — `restore` and `rollback --mode full` run destructively with no confirmation

**Affected:** `main.py:99-132` → `services/restore.py` (`run_restore`) / `services/rollback.py` (verified by sub-agent; consistent with F3).

`odooctl restore staging` immediately drops+recreates the live target DB and replaces the filestore with **no `--yes`, no `--preview`, no typed confirm**. `rollback --mode full` restores DB+filestore and only prints a warning (no prompt). Compare `promote` and `env destroy`, which *do* require `--yes`. The confirmation model is inconsistent across destructive commands.

**Remediation:** Require `--yes` (and offer `--preview`) on `restore` and `rollback --mode full`, matching `promote`/`env destroy`.

---

### F12 — LOW — Capability-token replay window and nonce store growth

`api/routes_operations.py:141` mints capability tokens with `ttl_seconds=3600` (1 hour), while `security/tokens.py` defaults to 300s and its docstring stresses "keep TTLs short." Replay for the **runner** path is mitigated by single-use nonces (`runner/worker.py:162-171`), but `NonceStore` (`worker.py:63-91`) "grows unbounded" (acknowledged in-code) — a slow disk-growth / DoS vector — and the **API read endpoints do not consume nonces**, so a captured read token is replayable for its full hour. **Remediation:** lower the capability-token TTL toward the 300s default; add TTL-based nonce purging; consider short-lived API session tokens.

### F13 — LOW — Audit chain is unkeyed and tail-truncation is undetectable

`operations/audit.py:12-15` hashes entries with **unkeyed** SHA-256; `verify_chain` (`:62-72`) recomputes the whole chain from `prev_hash=""` forward. So anyone able to rewrite `audit.jsonl` can forge a clean chain (tamper-*evident* against naive edits/3rd-party tools, not tamper-*proof*), and **deleting the last N lines still verifies** (no length/anchor commitment). Concurrency is correctly guarded by `fcntl.flock`. **Remediation:** use an HMAC keyed with a runner-only key and commit a monotonically increasing sequence number + count so truncation is detectable; document the WORM limitation.

### F14 — LOW — Self-validating backup manifest; restore path not confined to backups root

`services/restore.py:40-70` recomputes file checksums and compares them to values in the **same** `manifest.json` inside the backup dir — an attacker who can write the backups directory supplies both a malicious `db.dump`/`filestore.tar` and matching checksums, and validation passes (no signature/HMAC over the manifest). `resolve_backup_dir` (`:31-33`) returns `backups_root / backup` for any non-"latest" value with **no containment check**, so a `backup` like `../../x` escapes the backups root (then constrained only by the three-file + self-checksum requirement). **Remediation:** HMAC-sign manifests with a runner key; `resolve()` the backup dir and assert it is under `backups_root`.

### F15 — LOW — Healthcheck follows redirects and treats any 3xx as healthy

`odoo/healthcheck.py:18-36` uses `urlopen` (default redirect handler) and returns `True` for `200 ≤ status < 400` and for caught 3xx. A misconfigured proxy returning a redirect — or a redirect to an internal host / cloud metadata endpoint — is reported "healthy" without the app ever responding, masking failed deploys and making the post-deploy gate (which guards rollback decisions) unreliable. The seed URL is operator config, so this is SSRF-adjacent rather than classic SSRF. **Remediation:** disable redirect following and require a 2xx (ideally an expected status/body marker).

### F16 — LOW — Redaction gaps and divergence

`utils/shell.py:38` skips redaction for secret values shorter than `min_secret_length` (default 6) or in the ignore list (`DEFAULT_REDACTION_IGNORE_VALUES` includes `password`, `changeme`, `admin`, `postgres`, `secret`) — a 5-char production token appears in logs in cleartext (documented in `SECURITY.md`, but a real residual). There are **two** independent redactors (`utils/shell.py` env-name-based; `security/redaction.py` value/key-based) with **different** token lists, and the API enqueue path calls `redact(body.params)` with no `secret_values`, so a literal secret under a non-secret-looking key passes through. **Remediation:** unify on one redaction module and one secret-token list; feed resolved secret values into the redactor on log/audit/API error sinks.

### F17 — LOW — Duplicated inline literal-escaping

`adapters/db.py:94` re-implements `'`→`''` escaping inline for `terminate_sql` instead of reusing `odoo/db_swap.quote_literal`. The escaping is currently correct (single-quoted literal), but duplicated/drifting escaping logic is a latent hazard. **Remediation:** reuse the shared helper.

### F18 — LOW — Schedule generator interpolates unvalidated fields into cron lines

`commands/schedule.py:82-96` emits `f"{cron_expr} {spec.user} {cd_and_run}\n"` with `interval`/`user`/`odooctl_bin`/`project_root` interpolated **unquoted and unvalidated** (env names *are* validated). A crafted `--interval "0 2 * * * root /bin/evil #"` or a value containing a newline injects an extra cron line; an unquoted path with spaces breaks the line. This is an operator-supplied footgun (writing their own crontab), not a boundary crossing. **Remediation:** validate the cron-expression shape, reject newlines, and shell-quote paths.

### F19 — LOW — Migration report filename path traversal

`migration/rehearse.py:223-228` builds a report filename from `source_env`/`source_version`/`target_version` and joins via `report_dir / fname` with no sanitization, so a `source_env` containing `../` could write the JSON report outside `report_dir`. Operator-supplied, low impact. **Remediation:** slugify the components (`re.sub(r"[^A-Za-z0-9._-]", "_", …)`).

### F20 — LOW — `import --output … --force` writes anywhere

`importer/adopt.py:26-31` writes generated YAML to a caller-supplied `output_path` (CLI `--output`), and `--force` removes the only guard (the exists-check). No root containment. Operator-controlled (writes config the operator already controls to a path they choose), but no defense in depth. **Remediation:** confine output under the project/cwd or require an explicit absolute-path opt-in.

### F21 / F22 / F23 / F24 — Observations

- **F21:** `runner_contract.PRIVILEGED_MODULE_PREFIXES` covers `odooctl.adapters` / `odooctl.odoo` only. An API module importing `odooctl.services.clone` (which *transitively* imports adapters) would **not** be flagged, because the AST check is per-file and matches only direct imports. The real boundary is the process split, so this is defense-in-depth, but the gap is worth closing (add `odooctl.services`, `odooctl.runner`, `odooctl.operations.engine` to the prefix list, or check transitively). The module docstring also still says "There is no API package yet," which is stale (M12/M13 shipped `odooctl.api`/`odooctl.web`).
- **F22 (docs drift):** `docs/web-ui.md:63` shows `odooctl security token mint --role operator`, but `commands/security.py:209-218` makes `--action/--env/--project` **required** and defaults `--key-env` to **`ODOOCTL_RUNNER_KEY`**, while the API verifies with `ODOOCTL_API_KEY` (`api/auth.py:30-32`) — copy-pasting the documented command either errors or mints a token the API rejects. `docs/web-ui.md:57` shows `serve --host 0.0.0.0` (encourages binding all interfaces; the only real gate then is the bearer token, since `TrustedHostMiddleware` filters Host headers, not the bind). `app.py`'s "binds to localhost-only via TrustedHostMiddleware" comment conflates Host-header filtering with socket binding, and `testclient` is permanently in the default `allowed_hosts`.
- **F23 (ergonomics):** the global short flag `-p`/`--project` (`main.py:70`) collides with `serve`'s local `-p`/`--port` (`main.py:270`) — same letter, different meaning per subcommand. The most destructive live-DB commands (`deploy`, `restore`, `rollback`, `backup`, `update-modules`) have **no `--dry-run`**, while less destructive ones (`init`, `clone`, `promote`, `import`) do.
- **F24:** `serve`/`runner` accept any non-empty `ODOOCTL_API_KEY`/`ODOOCTL_RUNNER_KEY` — no minimum length/entropy floor on the HMAC key that protects the entire HTTP surface and signs every capability token. `doctor` checks referenced config secrets but not these keys.

---

## 5. Feature / implementation quality observations

- **Coherent, layered architecture.** Clear separation of `adapters/` (Docker/Postgres/filestore/S3/proxy), `odoo/` (sanitize/db-swap/healthcheck/module-update), `services/` (orchestration), `commands/` (CLI), `api/` + `runner/` (control plane), `security/` (identity/RBAC/tokens/secrets/redaction). Dependency direction is sensible and the privileged/unprivileged split is real (separate processes, capability tokens).
- **Strong test posture.** 46 test modules; per project memory the suite is ~520 tests. Notable hardening tests exist (`tests/test_import_hardening.py` monkeypatches `subprocess`/`os.system`/network to assert the importer is side-effect-free; redaction regression tests assert literal secrets/`${VAR:-default}` defaults never reach output). The RBAC matrix is asserted against `role_matrix()`.
- **The "correct" patterns already exist in-tree** — they're just applied inconsistently. `restore_to_env` (atomic temp-DB-then-swap, `is_protected`-aware) is the model the other destructive flows should follow; `db_swap.quote_identifier`/`quote_literal` is the SQL-identifier pattern the inline escaping (F17) and the `sh -lc` clone (F1) should reuse; the OpenUpgrade **pinned-branch allow-list** (`migration/openupgrade.py`) is exactly the right way to keep version strings out of commands.
- **Config model is rich and self-validating** (cross-environment uniqueness for db_name/filestore/domain/branch, clone-graph integrity, promotes-to checks) — but stops short of **value/charset validation** of the same fields, which is the gap behind F1/F8.
- **Importer is conservative**: read-only detection, env-var references instead of literal passwords, structured-dict + `yaml.dump` rendering (no string templating), `yaml.safe_load`/`tomllib` everywhere.
- **Documentation is unusually complete** for an alpha (per-feature docs, SECURITY.md, runner architecture, RBAC matrix), which is what makes the drift items (F2 vs README, F22) worth fixing — the docs set expectations the code doesn't yet meet uniformly.

---

## 6. Security posture review by category

**Auth / permission boundaries.** RBAC matrix and the protected-environment admin floor are well-modeled (`security/rbac.py`) and — importantly — the **floor is now enforced at both the API enqueue (`routes_operations.py:110`) and re-checked in the runner (`worker.py:155`)**, remediating the M12-blocked gap. Capability tokens are HMAC-SHA256, constant-time compared, with no algorithm-confusion (the verifier never reads `alg` from the header) and roles re-derived server-side from the signed payload. Gaps: `cancel` gated by a read action and no per-project/org scoping (F6); 1-hour capability TTL and unbounded nonce store (F12); no key-strength floor (F24).

**Secrets handling.** Good primitives: encrypt-then-MAC stdlib store, `SecretValue` wrapper that refuses implicit reveal, `0600` files created without a permission race, env-var references in config, and **no secrets committed** (all flagged matches are placeholders/`*_env` names; `.odooctl/` is gitignored). Weaknesses: the DB password on `--db_password` argv leaking through unredacted `CommandError` into API-exposed errors (F5); master key co-located with ciphertext (F9); short-secret redaction gap and two divergent redactors (F16).

**Shell / command safety.** Almost entirely list-argument subprocess with no shell; DB credentials passed via `PGPASSWORD` env (not argv) in the Postgres adapter. The exceptions are the three `sh -lc` f-string sinks (F1) and the `--db_password` argv (F5). No `os.system`/`eval`/`exec`/`pickle`/`yaml.load` anywhere in product code (repo-wide grep).

**Backup / import / restore / deployment-sensitive flows.** This is the weakest area. Drop-before-verify with no rollback (F3), failed-deploy backup never restored (F4), literal-"production" guards (F2), self-validating manifests + unconfined restore path (F14), and missing confirmations (F11). Backups themselves are real (db.dump + filestore.tar + SHA-256 checksums), and `restore_to_env`/`run_dr_drill` are safe models. Sanitization is safe-by-default but incomplete in important corners (F7).

**Container / runtime exposure.** API binds `127.0.0.1` by default with a required non-empty key; SPA path traversal is guarded by `relative_to` after `resolve()`. But `TrustedHostMiddleware` only filters Host headers (not the bind), the docs encourage `--host 0.0.0.0` (F22), and the F1 injection executes **inside** the Postgres/Odoo container — a container boundary that matters most under the multi-tenant runner model.

**Weak defaults.** `execution_mode: host` (so the docker-only F1 path is off by default — good); `sanitize: false` at the env level (the service default is `True` and the config example sets `sanitize: true`, but an env that omits it won't sanitize unless the literal-"production" guard fires — see F2); capability TTL 1h; redaction ignore-list contains common secret-ish values; no key-strength floor.

**API / CLI ergonomics.** Generally clean Typer CLI. Rough edges: inconsistent confirmation across destructive commands (F11), `-p` overload and missing `--dry-run` on destructive commands (F23), and token-mint commands that don't match their own docs (F22).

**Docs / implementation drift.** The headline README safety promise is not uniformly enforced (F2); runner-architecture/runner-contract docs are stale about the (now-shipped) API surface (F21); token-mint and `serve` examples don't match the CLI (F22). RBAC docs, localhost-bind default, and the backup artifacts claim are accurate.

---

## 7. What is done well (credit)

- Protected-env destructive floor enforced at **both** API enqueue and runner (defense-in-depth; M12 remediation confirmed).
- HMAC capability tokens: constant-time compare, no alg-confusion, server-side role re-derivation, single-use nonce enforcement at the runner.
- List-argument subprocess everywhere except three sinks; `PGPASSWORD` via env in the Postgres adapter.
- Encrypt-then-MAC secret store, `SecretValue` wrapper, `0600`-without-race file writes.
- `yaml.safe_load`/`tomllib` throughout; side-effect-free importer that refuses to inline literal passwords (test-enforced).
- flock-guarded, hash-chained audit log; `O_EXCL` per-environment locks with stale-PID detection.
- `restore_to_env` (atomic temp-DB-then-swap, `is_protected`-aware) and `run_dr_drill` (throwaway DB, always dropped) are correct, safe models.
- SQL identifier quoting (`db_swap.quote_identifier`/`quote_literal`) and OpenUpgrade pinned-branch allow-list are the right patterns.
- SPA static serving has a real path-traversal guard.

---

## 8. Open questions & recommended next steps

**Open questions for the maintainers:**
1. **Threat model for project config.** In the API/runner deployment, can the set of registered projects / their `db_name`/`domain`/`filestore_path` be influenced by anyone less trusted than the runner operator (multi-tenant, self-service onboarding, imported third-party compose)? The answer moves F1/F8/F10 between High and Critical.
2. **Is multi-tenant isolation in scope for the current release?** `org_id` is modeled but unenforced (F6). If yes, reads/cancels need scoping now.
3. **Intended `execution_mode` for real deployments.** F1's most dangerous sink (`clone_db_in_container`) is docker-mode only; how common is `execution_mode: docker` in practice?

**Recommended next steps, in priority order:**
1. **Add identifier/hostname validators** to `EnvironmentConfig` (`db_name`, `filestore_path`, `filestore_volume`, `domain`) and `SanitizationConfig.temp_db_suffix`; **remove the three `sh -lc` strings**. (Closes F1, hardens F8.)
2. **Replace every literal `== "production"` with `cfg.is_protected(...)`** and add a regression test for a `tier: production` env not named "production." (Closes F2; partially F4.)
3. **Make `run_restore` and `swap_temp_database` verify-before-destroy with rollback**, and restore-on-failure for production deploy. (Closes F3, F4.)
4. **Stop putting the DB password on argv; redact `CommandError.args` and persisted/emitted operation errors.** (Closes F5.)
5. **Introduce a write-family `CANCEL` action; scope reads/cancels by org/project before enabling multi-tenant.** (Closes F6.)
6. **Sanitization:** set `web.base.url.freeze`, cover `payment_acquirer`, keep crons disabled under `minimal`, disable OAuth/SMS. (Closes F7.)
7. **Require `--yes`/`--preview` on `restore` and `rollback --mode full`;** unify the confirmation model. (Closes F11.)
8. **Lower capability TTL, purge nonces, HMAC-sign audit + backup manifests, confine restore/import/report paths, fix healthcheck redirects, unify redaction, add a key-strength floor, refresh the drifted docs.** (F12–F24.)

---

*End of report. Generated by an automated audit agent (Claude Opus 4.8); all line references verified against commit `9e39a95` on `master`.*
