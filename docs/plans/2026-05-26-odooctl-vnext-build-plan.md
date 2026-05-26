# odooctl v-next: Installed Agent + Docker-Native Environments — Build Plan

**Date:** 2026-05-26
**Status:** Proposed — planning only, no code changed by this document.
**Audience:** internal. Direct, architectural, actionable by a coding agent.
**Provenance:** Code-verified pass over the current MVP (every file read) + `experiments/odoo19-community-staging/README.md`.

> **Supersedes** the earlier same-day draft `2026-05-26-installed-agent-and-docker-native-environments.md`.
> That draft is directionally correct but contains code-level inaccuracies (see §0.1). Recommend archiving or
> deleting it so there is one source of truth. This document is the authoritative build plan.

---

## 0. TL;DR — what to build, in what order

**Product goal:** install `odooctl` once on a server, point it at a tracked Odoo repo, and let operators create/manage named environments (`production`, `staging`, `qa`, `dev`) — deploy, clone prod→stage, sanitize, rollback, health-check.

**Blunt reality from the Odoo 19 experiment:** the engine does not yet work against a real Docker Odoo stack. `backup`, `clone`, and `update-modules` all failed because the tool assumes host PostgreSQL client tools + host DB connectivity, and assumes HTTPS. A globally-installed CLI that cannot clone prod→staging on a real Docker box is a demo, not a product.

**Decision: fix the engine first, then wrap it in the installed-agent / multi-project surface. Distribution polish last.**

| Phase | Milestone | Why this order |
|---|---|---|
| **M0** | Test-harness hygiene (env isolation, conftest, markers) | Unblocks safe TDD; fixes a live test bug (gap #9). ~0.5 day. |
| **M1** | `ProjectContext` (de-cwd the whole tool) + `odooctl doctor` | Latent correctness bug *and* the product's foundation. Makes every later failure legible. Experiment's #1 ask. |
| **M2** | Docker-native execution mode (DB + Odoo flags + scheme) | The core unblock. After this, real backup/clone/update work on Docker Odoo with **no host pg-client**. |
| **M3** | Safe clone choreography + multi-db mode + filestore-volume awareness | Correctness + the dev/qa/staging-on-one-box workflow. |
| **M4** | Global install: project registry + `env` lifecycle | The headline product surface, built on M1. |
| **M5** | Distribution (PyPI/pipx/uv), scheduled ops, redaction fix, real S3, docs, integration CI | Make it a product people install and run unattended. |

**Packaging (detail §5):** publish to PyPI; primary path `pipx install odooctl` (the `npm i -g` of Python); modern alt `uv tool install odooctl`. **No npm wrapper. No long-running daemon.** Use generated **systemd timers / cron** for scheduled backups and health polls. Default to **container execution mode** so pipx users never need host `pg_dump`.

### 0.1 Code-verified corrections to the earlier draft (why this one is authoritative)

These are not nitpicks — each one changes what the implementing agent must touch.

1. **cwd coupling is far deeper than "the compose adapter."** `DockerComposeAdapter` *already* passes `cwd=self.project_dir` in every method (`adapters/docker_compose.py`). The real coupling is that **commands construct `DockerComposeAdapter(cfg.runtime.compose_file)` with no `project_dir`**, **git calls omit `cwd`**, and critically **`MetadataStore()`, `backups.local_path`, sanitization `sql_files`, and `odoo.config_path` are all cwd-relative**. M1 must root *all* of these, not just compose.
2. **State does NOT currently live in the repo.** `MetadataStore(root=".odooctl")` is constructed bare in `status/deploy/backup/rollback` → `.odooctl/` is created in **cwd**. The prior draft's Q3 ("state currently lives in the repo, lean: keep it there") rests on a false premise; today it lives wherever you happen to `cd`. M1 fixes this by rooting it at `ProjectContext.root`.
3. **`status.py` hardcodes the DB service name `"postgres"`** (`_service_status(ps, "postgres")`), but real stacks (incl. the experiment) name the service `db`. **PostgreSQL status is always reported "unknown" today.** Real bug; fixed in M2 by sourcing the service name from config.
4. **Binary corruption is a *new-path* risk, not current.** Host-mode `pg_dump -f <file>` / `pg_restore <file>` use file args — bytes never flow through Python's text pipe. The `utils/shell.run` redaction hazard applies only to the **new container-streaming** path (M2). The prior draft implies host mode is already at risk; it is not.
5. **Tests monkeypatch `DockerComposeAdapter` with single-arg lambdas** (`lambda compose_file: compose`). Threading `project_dir`/context through the constructor **breaks these monkeypatches**; M1 must update them. The prior draft's "no behavior change, guarded by existing tests" understates this.
6. **`update_modules_local` (host `odoo`) is dead code** — defined and unit-tested, never called by a command. The live path is `update_modules_compose`. Don't spend effort on the host path unless we add a host execution mode.

---

## 1. Verified current-state map

### 1.1 Package / CLI
- `pyproject.toml`: hatchling, `requires-python >=3.11`, deps `typer>=0.12 / pydantic>=2 / pyyaml>=6 / rich>=13`, `dev` extra `pytest>=8 / ruff>=0.6`, entry point `odooctl = odooctl.main:app`. **No PyPI metadata** (no `license`, `authors`, `classifiers`, `urls`, `keywords`). `[tool.pytest.ini_options]` has only `testpaths`; **no markers**.
- `odooctl/main.py`: Typer app, `--version` via `importlib.metadata`. Commands: `init, deploy, backup, restore, clone, update-modules, rollback, logs, status, validate, github-actions`. Every command takes `config: str = "odooctl.yml"` resolved **relative to cwd**. No `-C/--project-dir`, no project concept.
- `odooctl/__main__.py`: enables `python -m odooctl`.

### 1.2 Config (`odooctl/config.py`)
- Models: `ProjectConfig, RuntimeConfig, EnvironmentConfig, PostgresConfig, OdooConfig, RemoteBackupConfig, RetentionConfig, BackupsConfig, SanitizationConfig, HealthcheckConfig, OdooCtlConfig`.
- `PostgresConfig`: single host-oriented block (`host/port/user/password_env`); `password()` reads `os.getenv`. **No in-container access concept.**
- `EnvironmentConfig`: `branch, domain, db_name, filestore_path, clone_from, sanitize, update_modules`. **No `scheme`, `port`, `stack`, `db_selector`.**
- `OdooConfig`: `image, config_path, addons_paths, service`. **No DB-flag fields, no filestore container path, no `without_demo`.**
- `validate_environment_graph`: enforces **unique** `db_name`, `filestore_path`, `domain`, `branch` across envs; forbids `production` as a clone target; validates `clone_from` references. The unique-`domain` rule blocks single-service multi-db local staging (gap #4).
- `load_config(path)` reads relative to cwd. `referenced_env_vars()` / `missing_env_vars()` drive preflight (covers `postgres.password_env` + remote backup envs).

### 1.3 Adapters (`odooctl/adapters/`)
- `docker_compose.py` — `DockerComposeAdapter(compose_file, project_dir=None)`; `pull/build/up/restart/logs/ps/exec`. **`exec` already uses `-T`.** Every method passes `cwd=self.project_dir` — but callers never set `project_dir`.
- `postgres.py` — `PostgresAdapter` shells to **host** `psql/pg_dump/pg_restore/dropdb/createdb` with `PGPASSWORD`. `dump()` uses `-Fc -f <file>`; `restore()` does `drop_create` then `pg_restore <file>`. **No container backend** (root cause of gaps #1, #5).
- `filestore.py` — `FilestoreAdapter`: host-path `tar --zstd` + `shutil`. **No Docker-volume awareness** (gap #6).
- `reverse_proxy.py` — `public_url(domain)` hardcodes `https://` when no scheme present (gap #3). Ignores `runtime.reverse_proxy`.
- `s3.py` — `S3Adapter` is a **local-mirror stub** (copies into `.odooctl/remote-backups/<bucket>/`), not real S3.

### 1.4 Odoo logic (`odooctl/odoo/`)
- `sanitize.py` — `default_sql/profile_sql/sanitize_database`. Disables `ir_mail_server`, `fetchmail_server`, `ir_cron`, `payment_provider`; scrubs webhook/secret `ir_config_parameter`; rewrites `web.base.url`. Profiles `minimal|normal|strict`. **Runs statement-by-statement against the live target DB** (one `psql -c` per statement). `sql_files` resolved relative to **cwd**. **Does not disable OCA `queue_job` or flush the `mail.mail` spool** (see §10).
- `module_update.py` — `update_modules_compose` runs `odoo -d <db> -u <mods> --stop-after-init` inside the service with **no DB flags** → fails on the official image (gap #2). `update_modules_local` is dead code.
- `healthcheck.py` — `check_url` urllib GET, retries/interval, accepts 200–399. **No `?db=` selector** (gap #4).

### 1.5 Commands (`odooctl/commands/`)
- `deploy.py` — `_preflight`: missing-env, branch match, **compose exists (resolved relative to config dir)**, host filestore_path exists, **host Postgres ping**, clean worktree. Then prod backup → `git fetch/checkout/pull` (**no cwd**) → `compose.pull/up` (**compose adapter built with no project_dir**) → `update_modules_compose` → healthcheck → metadata. Prod failure → `compose.restart`. **Latent bug:** preflight checks the compose path relative to the config dir, but execution runs `docker compose -f <relative>` in cwd — these can diverge.
- `clone.py` — validates `clone_from`, refuses prod-source clone without sanitize; **dumps source then `restore()` (drop_create) directly into the live target `db_name`**; `fs.copy` host paths; sanitizes the now-live DB; `update_modules_compose`; `compose.restart`; `ps` check; healthcheck. **No temp DB / swap** (gap #7). `--preview` is side-effect-free and useful.
- `backup.py` — host `pg.dump` → `backup_dir/db.dump`; filestore tar; redacted `odoo.conf` snapshot (`SENSITIVE_CONFIG_KEYS`); manifest with sha256 checksums; S3 mirror; retention prune. `backups.local_path` relative to **cwd**.
- `restore.py` — resolve/validate backup dir (required files, project/env match, checksum verify) → host `pg_restore` (drop_create) + filestore extract → healthcheck.
- `rollback.py` — `code` (checkout `previous_successful_deployment` commit, detached HEAD; clean-worktree gate; cross-branch refusal) or `full` (restore backup; requires `--backup`). Records rollback metadata.
- `status.py` — `compose ps` + metadata → human/JSON. **Hardcodes DB service `"postgres"`** (bug, see §0.1). `public_url` → HTTPS.
- `validate.py` / `init.py` / `github_actions.py` / `logs.py` / `update_modules.py` — load config + report; write `example_config()`; render a `workflow_dispatch` deploy workflow; tail compose logs; thin update wrapper.

### 1.6 Metadata (`odooctl/metadata/`)
- `store.py` — `MetadataStore(root=".odooctl")` JSON store: `deployments/` + `backups/`, `*-latest.json` pointers, `previous_successful_deployment`. **Default root is cwd-relative; constructed bare everywhere** → state lands in cwd, not the repo (§0.1 #2).
- `models.py` — `BackupManifest` (schema_version, checksums, mode, …) + `DeploymentMetadata` (status, commit, image, backup, message, …). `.odooctl/` and `backups/` are gitignored.

### 1.7 Utils (`odooctl/utils/`)
- `shell.py` — `run(...)` is **text-mode**; `stream=True` reads lines and **redacts every sensitive-keyed env value via global `str.replace`**. Consequences: (a) it would **corrupt a binary `pg_dump -Fc` stream** routed through it (relevant only to the new container path); (b) redaction nukes common tokens like `odoo` when used as a password (gap #8). `SENSITIVE_MARKERS = PASSWORD/SECRET/TOKEN/KEY/PASSWD`.
- `paths.py`, `logging.py` — `ensure_dir`, `success/warn` helpers.

### 1.8 Tests (`tests/`, 16 files, ~97 tests)
- All **unit-level**, fully monkeypatched (`DummyCompose/DummyPostgres/DummyFilestore/DummyStore/DummyConsole` redefined per file). **No `conftest.py`, no markers, no Docker integration.** Sensitive to a real exported `ODOO_DB_PASSWORD` (gap #9): `test_deploy_missing_env_vars_*` does **not** monkeypatch `PostgresAdapter`, so when the var is set in the ambient env the test sails past the missing-env gate and hits the *real* `psql`, exploding on a missing host binary.

### 1.9 Experiment stack (the integration fixture, ground truth)
`experiments/odoo19-community-staging/docker-compose.yml`: services **`db`** (`postgres:17`, `pg_isready` healthcheck, volume `postgres-data`, **port not published to host**) and **`odoo`** (`odoo:19.0`, env `HOST=db USER=odoo PASSWORD=…`, port `18069:8069`, volumes `odoo-data:/var/lib/odoo` + `./addons:/mnt/extra-addons`). Odoo 19.0-20260513, PostgreSQL 17, 695 base modules. DB port is **not** on the host → host pg-client cannot reach it → **container mode is mandatory** for this (representative) topology.

---

## 2. Target product model

Three nouns, made explicit:

1. **The agent / CLI** — `odooctl`, installed once globally (pipx/uv tool). Stateless, on-demand. Discovers projects via a small global registry.
2. **A tracked project** — a git repo on the server with `docker-compose.yml`, `odooctl.yml`, addons, and (gitignored) `.odooctl/` state. The production server's repo *is* the production project; the same repo can describe additional stages.
3. **Named environments** — `production` (live) + operator-created `staging/qa/dev`. An environment = `{stack, branch, scheme+domain(+port), db_name, filestore, clone_from, sanitize, update_modules, db_selector}`. Environments either share one Docker stack (multi-db) or run as separate stacks (isolation) — see §11.

Operator mental model:
```
odooctl project add acme --path /srv/odoo/acme   # register the repo once
odooctl doctor -p acme                            # is this box ready?
odooctl env create staging --clone-from production --sanitize
odooctl deploy staging
odooctl status
```

**Scope boundary (decide now):** v-next targets **one server, one-or-more stacks on that server.** Environments on *different hosts* (remote SSH execution) are **out of scope** (open question Q5). The `ExecutionContext` seam introduced in M2 leaves room to add a remote backend later without rework.

---

## 3. Required refactors (the honest list)

Not optional polish — the product direction cannot land without these.

1. **De-cwd the entire tool.** Introduce `ProjectContext(root)` and thread it through: compose `project_dir`, every `git` `run(cwd=root)`, `MetadataStore(root/".odooctl")`, `backups.local_path`, sanitization `sql_files`, `odoo.config_path`, and host filestore paths. *(M1 — broad blast radius; do it behind M0's hardened tests.)*
2. **Split host vs container DB access.** One `PostgresConfig` cannot describe both "how the operator reaches PG" and "how Odoo/psql reach PG inside the compose network." Add a container access block + `execution_mode`. *(M2)*
3. **Add container execution backends** for DB + filestore (run through `docker compose exec`/`cp`/`tar` pipes). *(M2/M3)*
4. **Binary-safe command runner.** Add byte-capture / stdin-stream runners; keep text `run` for everything else. *(M2)*
5. **Scheme as data, not assumption.** Per-env `scheme`; propagate to healthcheck, status, sanitize base-url rewrite, clone preview. *(M2)*
6. **Fix the `status` DB-service bug** — source the service name from `postgres.service`, not the literal `"postgres"`. *(M2)*
7. **Safe clone choreography** — temp-DB restore → sanitize → atomic swap. *(M3)*
8. **Relax domain-uniqueness for multi-db stacks** while keeping `db_name`/`filestore` uniqueness always. *(M3)*
9. **Project registry subsystem** + `project`/`env` command groups. *(M4)*
10. **Redaction precision** — don't blanket-replace short/common secret values. *(M5)*

---

## 4. Target config schema (v2 — additive, backward compatible)

All new fields are **optional with safe defaults**, so existing `odooctl.yml` keeps loading (see §14). North-star, annotated:

```yaml
project:
  name: acme
  odoo_version: "19.0"
  # repo path is NOT here — it lives in the global registry (project binding).

runtime:
  type: docker_compose
  compose_file: docker-compose.yml
  reverse_proxy: traefik
  execution_mode: docker        # NEW: docker | host. Default: docker when type == docker_compose.

postgres:
  # Host-side access (execution_mode: host, and operator-run psql)
  host: localhost
  port: 5432
  user: odoo
  password_env: ODOO_DB_PASSWORD
  # Container-side access (execution_mode: docker)
  service: db                   # NEW: compose service running PostgreSQL (also fixes status bug)
  internal_host: db             # NEW: hostname used *inside* the compose network
  # service_user / service_password_env default to user / password_env

odoo:
  image: odoo:19.0
  config_path: ./odoo.conf
  service: odoo
  addons_paths: [/mnt/extra-addons]
  db_host: db                   # NEW: --db_host for in-container `odoo` (default: postgres.internal_host)
  db_user: odoo                 # NEW: --db_user (default: postgres.user)
  db_password_env: ODOO_DB_PASSWORD  # NEW: source for --db_password (default: postgres.password_env)
  filestore_container_path: /var/lib/odoo   # NEW: filestore root inside the odoo container
  without_demo: "True"          # NEW: Odoo 19 syntax (replaces deprecated 'all')

environments:
  production:
    stack: prod                 # NEW: which compose stack this env belongs to
    branch: main
    scheme: https               # NEW: http | https (default https)
    domain: odoo.example.com
    # port: 443                 # NEW (optional): explicit host port appended to URLs
    db_name: odoo_prod
    filestore_path: /var/lib/odoo/filestore/odoo_prod   # host path OR volume-relative subpath
    # filestore_volume: odoo-data   # NEW (optional): named docker volume holding the filestore
    update_modules: [sale, stock]
  staging:
    stack: prod                 # same stack => multi-db on one Odoo service allowed (non-prod only)
    branch: staging
    scheme: https
    domain: staging.odoo.example.com   # or SAME as prod when db_selector: true (multi-db local)
    db_name: odoo_staging
    filestore_path: /var/lib/odoo/filestore/odoo_staging
    clone_from: production
    sanitize: true
    db_selector: false          # NEW: when true, append ?db=<db_name> to healthcheck URL (multi-db)

sanitization:
  sql_files: [.sanitize/staging.sql]   # resolved relative to PROJECT ROOT (M1), not cwd
  disable_mail_servers: true
  disable_fetchmail: true
  disable_crons: true
  disable_payment_providers: true
  disable_queue_jobs: true      # NEW: OCA queue_job.job + base_automation (see §10)
  purge_mail_queue: true        # NEW: delete unsent mail.mail spool
  rewrite_base_url: true
  temp_db_suffix: _incoming     # NEW: name used during the safe clone swap

healthcheck:
  path: /web/login
  scheme: ~                     # NEW (optional): override env scheme for probes
  timeout_seconds: 5
  retries: 12
  interval_seconds: 5

redaction:                      # NEW block (M5)
  min_secret_length: 6          # don't redact shorter values
  ignore_values: [odoo, postgres, admin]
```

**Validator changes (`config.py:validate_environment_graph`):**
- `db_name` and the resolved filestore identity (`filestore_path`, or `filestore_volume`+subpath) stay unique **always**.
- `domain` (and `branch`) uniqueness enforced **only across different `stack`s**, OR within a stack when `db_selector` is false. Two envs may share a `domain` **iff** they share a `stack` and both set `db_selector: true`.
- `production` remains forbidden as a `clone_from` target.
- A model validator default-fills `odoo.db_host/db_user/db_password_env` from `postgres.*` when omitted, and `postgres.service_user/service_password_env` from `user/password_env`.

---

## 5. Packaging & distribution (the "global install" requirement)

**Recommendation, ranked:**
1. **Publish to PyPI; install with `pipx`.** `pipx install odooctl` is the Python `npm i -g`: isolated venv, on PATH, `pipx upgrade odooctl`. Primary, documented path.
2. **`uv tool install odooctl`** — modern, faster, identical UX. Document both; they coexist.
3. **`pip install --user odooctl`** — fallback only (PATH/`~/.local/bin` caveats).
4. **Pinned/offline:** `pipx install odooctl==X.Y.Z` or install from a built wheel for air-gapped servers.

**Explicitly rejected:**
- **npm wrapper** — odooctl is Python; an npm shim adds a Node runtime dependency and a second pipeline for zero benefit and does nothing for the real dependency pain (pg-client/docker). Do not build it.
- **Long-running daemon (`odooctld`)** — unnecessary; the CLI is on-demand. For *scheduled* work, generate **systemd timers** (preferred on servers) or **cron** entries that invoke `odooctl backup` / `odooctl doctor --json`. A daemon is only justified if we later add inbound webhooks or a web UI (out of scope).

**The binary-dependency trap (address in docs + doctor):** pipx/uv install only Python. They will **not** bring `pg_dump`, `pg_restore`, `psql`, `docker`, or `tar --zstd`. Mitigation:
- **Default `execution_mode: docker`** so DB tooling runs *inside the `db` container* (image already ships the pg client). Removes the host pg-client requirement for the common case — directly fixing gap #1.
- `host` mode remains for operators whose PG is not in compose; `doctor` then checks host binaries and prints exact install hints.
- Optional thin `scripts/install.sh` (installs pipx/uv then odooctl) for a single curl-able command. Canonical instruction stays `pipx install odooctl`.

**`pyproject.toml` work (M5):** add `license`, `authors`, `classifiers`, `project.urls`, `keywords`; configure the hatchling version source; add `[project.optional-dependencies] s3 = ["boto3"]`; verify `odooctl --version` reads `importlib.metadata.version("odooctl")` post-publish.

---

## 6. Milestones

Each milestone ships on its own and leaves the tool working. **TDD throughout** (repo convention: write/adjust the failing test → implement → green → commit).

---

### M0 — Test-harness hygiene (~0.5 day)

**Objective:** make the suite robust to the real environment and ready for integration markers. Fixes gap #9.

**Files:**
- Create `tests/conftest.py`.
- Modify `pyproject.toml` (`[tool.pytest.ini_options]` markers + `addopts`).
- Touch only the test files that relied on ambient env (`tests/test_deploy.py`, and any of `clone/rollback/restore` that hit a real adapter when a secret is exported).

**Tasks:**
1. Add `tests/conftest.py` with an **autouse fixture** that `monkeypatch.delenv("ODOO_DB_PASSWORD", raising=False)` (plus other referenced secrets) unless a test opts in. Lift the repeated `DummyCompose/DummyPostgres/DummyFilestore/DummyStore/DummyConsole` into shared fixtures.
2. Register markers: `markers = ["unit", "integration", "docker"]`; add `addopts = "-m 'not integration'"` so default runs stay unit-only.
3. Re-home duplicated dummies; keep per-test overrides working.

**Acceptance criteria:**
- `pytest -q` passes with `ODOO_DB_PASSWORD` **set** in the environment and **unset** (today it fails when set).
- `pytest -m integration` collects 0 tests and exits clean.
- No new flakiness; existing assertions unchanged.

---

### M1 — `ProjectContext` (de-cwd) + `odooctl doctor` (~3–4 days)

**Objective:** the tool operates on a repo regardless of cwd, and `doctor` tells operators exactly why something will fail *before* it does. Experiment ask #1. **This is the foundation the registry (M4) and remote execution (future) plug into.**

**Refactor note (honest):** broad blast radius. Do it as a pure, no-behavior-change refactor guarded by M0's hardened tests. Tests monkeypatch `DockerComposeAdapter` with single-arg lambdas — those must be updated when the constructor/wiring changes.

**Files:**
- Create `odooctl/context.py` — `ProjectContext(root: Path, config_path: Path)`; `resolve(project_dir | cwd)` walks up for `.git`/`odooctl.yml`; `load() -> OdooCtlConfig`; helpers `compose_adapter()`, `metadata_store()`, `backups_root()`, `resolve_path(rel)` (root-anchored), `git(args)`.
- Create `odooctl/preflight.py` — composable checks returning `CheckResult(name, status: ok|warn|fail, detail, remediation)`.
- Create `odooctl/commands/doctor.py`.
- Modify `odooctl/main.py` — add `doctor`; add global `-C/--project-dir`; build a `ProjectContext` and pass it to commands.
- Modify `odooctl/commands/{deploy,clone,backup,restore,rollback,logs,status,update_modules}.py` — git/compose/path/state ops go through `ProjectContext` (`compose project_dir=root`, `run([...], cwd=root)`, `MetadataStore(root/".odooctl")`, `backups_root()`, `resolve_path()` for `sql_files`/`config_path`). **Reuse `preflight` in `deploy._preflight` and `clone`** instead of bespoke inline checks. Fix the deploy preflight/execution compose-path divergence.
- Fix `odooctl/commands/status.py` DB-service name to come from config (lands fully in M2 once `postgres.service` exists; in M1 at least stop hardcoding by reading `cfg.odoo`-adjacent service or defaulting).
- Create `tests/test_context.py`, `tests/test_doctor.py`; update `tests/test_deploy.py` (git calls now carry `cwd`; compose monkeypatch signature).

**`doctor` checks (each a `preflight` function):**
- docker + `docker compose` present; daemon reachable.
- compose file exists at project root; declared `odoo`/`db` services exist in it.
- execution-mode-appropriate DB connectivity (host `psql` ping OR `exec <db> pg_isready`).
- required host binaries **only if** `execution_mode: host` (`pg_dump/pg_restore/psql/createdb/dropdb`, `tar` w/ zstd) — print an install hint per missing binary.
- referenced env vars present (reuse `missing_env_vars`).
- filestore reachable (host path exists OR named volume exists OR container path readable).
- healthcheck URL scheme + reachability per env (**warn**, don't fail, if down).
- git repo present at root; report clean/dirty.
- **secret-quality warning** if a resolved secret is shorter than `redaction.min_secret_length` or in `ignore_values` (ties to gap #8).

**Acceptance criteria:**
- `odooctl -C /path/to/repo status` works from any cwd (no reliance on being inside the repo); `.odooctl/` and `backups/` are created **under the repo root**, not cwd.
- `odooctl doctor` on a healthy stack prints all-green, exits 0; with docker stopped or a binary missing, prints the failing check + remediation and exits non-zero.
- `odooctl doctor --json` emits a stable machine-readable check list (for cron/monitoring).
- All M0 tests green; `deploy`/`clone` tests updated for `cwd` threading and the new compose wiring.

---

### M2 — Docker-native execution mode (~4–5 days)

**Objective:** backup, restore, clone, and module-update all work against a real Docker Odoo 19 stack **with no host PostgreSQL client**. Fixes gaps #1, #2, #3, and the §0.1 status bug; sets up #5/#6.

**Refactor note:** load-bearing milestone. Introduce a DB execution-context abstraction + a binary-safe runner.

**Files:**
- Modify `odooctl/utils/shell.py` — add `run_capture_bytes(args, *, cwd, env, stdout_path)` and `run_pipe_stdin(args, *, cwd, env, stdin_path)`. **Binary-safe; no per-line text redaction on binary streams.** Keep the text `run`.
- Modify `odooctl/config.py` — add `execution_mode`; `postgres.service/internal_host/service_user/service_password_env`; `odoo.db_host/db_user/db_password_env/filestore_container_path/without_demo`; per-env `scheme/port/db_selector`; default-fill validator.
- Create `odooctl/adapters/db.py` — `make_db_adapter(ctx) -> DbAdapter` factory. `HostPostgresAdapter` (wraps the current `PostgresAdapter`) and `DockerPostgresAdapter` (runs `docker compose exec -T <db_service> …`), same interface: `ping/dump/restore/drop_create/psql/psql_file`, plus `clone_db_in_container(src, dst)` for the no-host-roundtrip path.
- Modify `odooctl/adapters/docker_compose.py` — add `exec_capture_bytes(service, args, stdout_path)` and `exec_pipe_stdin(service, args, stdin_path)` on the new runners; keep `-T`.
- Modify `odooctl/adapters/reverse_proxy.py` — `public_url(domain, scheme="https", port=None)`; callers pass env scheme/port.
- Modify `odooctl/odoo/module_update.py` — append `--db_host/--db_user/--db_password` (from `odoo.*`) to in-container `odoo`; or pass `-c <config_path>` when present.
- Modify `odooctl/odoo/healthcheck.py` — accept optional `db_param`; append `?db=<db_name>` when `db_selector`.
- Modify `odooctl/odoo/sanitize.py` — base-url rewrite uses scheme-aware `public_url`.
- Modify `odooctl/commands/{backup,restore,clone,status,update_modules}.py` — obtain DB adapter via `make_db_adapter(ctx)`; **fix `status` to use `cfg.postgres.service`** for the DB service status.
- Tests: `tests/test_db_adapter.py` (new); update `test_backup/test_restore/test_clone/test_module_update/test_healthcheck/test_status/test_config`.

**Key technical guidance (don't relitigate at code time):**
- **Container backup:** `docker compose exec -T <db> pg_dump -U <u> -Fc -d <db>` → capture **bytes** to a host file via `run_capture_bytes`. `-T` removes the TTY so stdout is clean. **Never route binary through the text `run`/redactor.**
- **Container restore:** stream the host dump to `pg_restore` stdin via `run_pipe_stdin` (`… exec -T <db> pg_restore -U <u> -d <db>`). Fallback: `docker compose cp` the dump in, then exec.
- **Container clone (fast path for M3 swap):** one exec — `exec -T <db> sh -lc 'pg_dump -Fc -d src | pg_restore -d dst'` — keeps data inside the container, no host round-trip.
- **Odoo invocation:** always pass `--db_host/--db_user/--db_password` (the experiment proved bare `odoo -d …` ignores the entrypoint's `HOST/USER/PASSWORD`).
- **`execution_mode: host`** keeps the current adapter path verbatim (no regression for non-Docker PG).

**Acceptance criteria:**
- On the experiment stack, with **no host `pg_dump`**, `execution_mode: docker`:
  - `odooctl backup production` produces a valid `db.dump` (round-trips through `pg_restore --list`) + filestore artifact + manifest.
  - `odooctl restore staging` restores that dump into the container DB and passes healthcheck.
  - `odooctl update-modules production --modules base` succeeds (no `default@default` socket error).
- `odooctl status` reports `http://localhost:18069` when `scheme: http`, **and reports PostgreSQL state correctly** for a service named `db`.
- `host` mode behavior unchanged (existing unit tests green).
- Byte-integrity test: a container-mode dump restores byte-faithfully (checksum or `pg_restore --list` assertion).

---

### M3 — Safe clone + multi-db mode + filestore volumes (~3–4 days)

**Objective:** clone prod→stage without disturbing a running Odoo; support "dev/qa/staging share one stack"; back up/restore filestores living in named Docker volumes. Fixes gaps #4, #6, #7.

**Files:**
- Modify `odooctl/commands/clone.py` — **temp-DB choreography**: restore/clone into `<db_name><temp_db_suffix>`; disable crons/mail/queue there; sanitize there; then **atomic swap** (terminate target connections → drop live target → `ALTER DATABASE … RENAME` temp→target) before restart/expose. Preview output shape unchanged.
- Create `odooctl/odoo/db_swap.py` — `terminate_connections` (`pg_terminate_backend` via `pg_stat_activity`), `rename_db`, guard against renaming onto `production`.
- Modify `odooctl/config.py` — relaxed domain/branch uniqueness for shared-`stack` + `db_selector` envs (§4); add `stack`.
- Modify `odooctl/adapters/filestore.py` — add `DockerVolumeFilestore`: archive via `exec -T <odoo> tar --zstd -cf - -C <filestore_container_path> filestore/<db>` → `run_capture_bytes`; restore reverse; clone via in-container `cp -a` or tar pipe. Factory `make_filestore_adapter(ctx, env)` picks host-path vs volume by `filestore_volume`.
- Modify `odooctl/odoo/sanitize.py` — add `disable_queue_jobs` (`queue_job` if present) and `purge_mail_queue` (`DELETE FROM mail_mail WHERE state != 'sent'`), guarded by `to_regclass` existence checks so they no-op on Community without those tables.
- Modify healthcheck callers — multi-db envs probe `?db=<db_name>`.
- Tests: `tests/test_clone_swap.py`, `tests/test_filestore_volume.py`; update `test_config` (multi-db validation), `test_clone`, `test_sanitize`.

**Acceptance criteria:**
- `odooctl clone production staging --sanitize` on the experiment stack: staging DB is built via temp DB, sanitized (crons/mail/payment/queue disabled, base-url rewritten, mail spool purged) **before** it is ever served; running Odoo logs show no cron/queue activity against a half-restored DB (the experiment's gap #7 symptom is gone).
- Swap refuses to operate on `production` as target; refuses if target connections can't be terminated (clear error).
- A config with two envs sharing `stack: dev` + `db_selector: true` + same `domain` **validates**; the same two without `db_selector` **fail validation** with a clear message.
- Backup/restore of an env whose filestore is a named volume works with **no host bind mount** present.

---

### M4 — Global install context: project registry + `env` lifecycle (~4–5 days)

**Objective:** deliver the headline UX — install once, track repos, create environments — on top of M1's `ProjectContext`.

**Files:**
- Create `odooctl/registry.py` — read/write `${XDG_CONFIG_HOME:-~/.config}/odooctl/config.toml` (system fallback `/etc/odooctl/config.toml`): `active` project + `projects.<name> = {path, config}`. Resolve `-p/--project <name>` → `ProjectContext`. Precedence **`-p` > `-C` > cwd**.
- Create `odooctl/commands/project.py` — `project add/list/use/remove/current`.
- Create `odooctl/commands/env.py` — `env list/show`, `env create <name> --clone-from <src> [--branch] [--domain] [--scheme] [--db-name] [--no-sanitize]`, `env destroy <name>` (never `production`; `--purge` drops DB/filestore behind confirmation). `env create` edits `odooctl.yml`, validates, then provisions via the M3 clone path.
- Modify `odooctl/main.py` — register `project` and `env` sub-apps; `-p` via registry, `-C` for ad-hoc/unregistered repos.
- Modify `odooctl/config.py` — a YAML round-trip writer for `env create/destroy` (see Q4).
- Tests: `tests/test_registry.py`, `tests/test_project_cmd.py`, `tests/test_env_cmd.py`.

**Tasks:**
1. Registry read/write + precedence resolution. Unit tests with a `tmp_path` XDG override.
2. `project` command group; tests assert registry mutations.
3. `env create` writes a valid env block → runs `validate` → calls clone (mocked in unit tests). `env destroy` removes the block + offers DB/filestore purge (guarded), refuses production.
4. Wire `-p` everywhere; ensure `.odooctl/` state stays in the **project repo** (now correctly rooted by M1), not the registry dir.

**Acceptance criteria:**
- `odooctl project add acme --path /srv/odoo/acme && odooctl -p acme doctor` works from `$HOME`.
- `odooctl -p acme env create qa --clone-from production --sanitize` adds a valid `qa` env, validates, and provisions it via the safe clone path.
- `odooctl env destroy production` is refused with a clear message; `odooctl env destroy qa --purge` removes config + DB + filestore after confirmation.
- Registry survives `pipx reinstall odooctl` (it lives under XDG config, not the package).

---

### M5 — Distribution, scheduled ops, polish (~3–4 days)

**Objective:** make odooctl installable from PyPI and runnable unattended; close gaps #8 and real S3.

**Files:**
- Modify `pyproject.toml` — PyPI metadata, `s3` extra (boto3), version source.
- Create `scripts/install.sh` — thin pipx/uv bootstrap (optional convenience).
- Create `odooctl/commands/schedule.py` — `odooctl schedule backup --env production --cron "0 2 * * *"` renders a **systemd timer+service** (preferred) or a crontab line invoking `odooctl backup`/`odooctl doctor --json`. Generation only; operator installs it. (Mirror the existing `github_actions.py` render-and-emit pattern.)
- Modify `odooctl/utils/shell.py` — redaction precision: skip values shorter than `redaction.min_secret_length` and those in `redaction.ignore_values`; never redact inside binary streams (already true after M2).
- Modify `odooctl/adapters/s3.py` — real S3 via boto3 behind the `s3` extra; keep local-mirror fallback when boto3/creds absent (warn).
- Docs overhaul (§8) + integration CI (§7).

**Acceptance criteria:**
- `pipx install dist/odooctl-*.whl` then `odooctl --version` works on a clean box with no repo present.
- `odooctl schedule backup --env production --cron "0 2 * * *"` emits a valid systemd timer pair (or `--cron-line` crontab entry) that, when installed, runs a backup.
- With `ODOO_DB_PASSWORD=odoo`, logs no longer redact the word "odoo" everywhere (gap #8), but a real 24-char secret is still redacted.
- `odooctl backup` with the `s3` extra + creds uploads to a real bucket; without, it warns and mirrors locally.

---

## 7. Test strategy

**Layers:**
1. **Unit (default, no Docker)** — current style, hardened by M0: shared fixtures in `conftest.py`, autouse env isolation, `@pytest.mark.unit`. All adapters faked. Every-PR gate.
2. **Integration (`@pytest.mark.integration` + `@pytest.mark.docker`)** — real Docker Compose using the **experiment stack as the fixture** (`odoo:19.0` + `postgres:17`). Session fixture in `tests/integration/conftest.py`:
   - skips unless `ODOOCTL_INTEGRATION=1` **and** `docker compose` available;
   - `compose up -d`, wait for `db` healthy + Odoo `/web/login`;
   - init `odoo_prod` (`odoo -d odoo_prod -i base --without-demo=True --stop-after-init` with DB flags);
   - yield a `ProjectContext` pointed at a temp copy of the experiment folder;
   - `compose down -v` on teardown.
3. **End-to-end clone assertion** (the test the experiment said was missing) — seed prod with representative outbound integrations (a fake `ir_mail_server`, a `payment_provider`, an `ir_cron`, a webhook `ir_config_parameter`, and a `mail.mail` in the spool), run `odooctl clone production staging --sanitize`, then assert in staging that mail/cron/payment/queue are disabled and secrets/base-url/spool are scrubbed.

**CI boundaries:**
- PR job: `pytest -m "not integration"` (fast, no Docker).
- Nightly / manual `workflow_dispatch`: `ODOOCTL_INTEGRATION=1 pytest -m integration` on a Docker-enabled runner.
- Lint: `ruff` on every PR.

**Coverage targets:** every new adapter/command ships unit tests; M2/M3 ship at least one integration test exercising the real container path; M3 ships the e2e sanitize assertion.

---

## 8. Docs / operator UX

Existing docs to **update**: `docs/installation.md`, `docs/configuration.md`, `docs/staging-clone.md`, `docs/backup-restore.md`, `docs/rollback.md`, `docs/security.md`, `docs/operations/deploy-staging-production.md`, `README.md` (command list + install).

**New docs to create:**
- `docs/getting-started.md` — the 5-command flow from §2.
- `docs/doctor.md` — every check, meaning, fix; `--json` schema for monitoring.
- `docs/environments.md` — lifecycle; **separate-stack vs multi-db** with the explicit production-isolation warning; when to use each.
- `docs/execution-modes.md` — `docker` vs `host`; the two DB-access contexts; required compose shape (service names `db`/`odoo`, filestore volume vs bind mount).
- `docs/odoo-versions.md` — Odoo 19 specifics (§10), `--without-demo` syntax, Community vs Enterprise images.
- `examples/multidb/{odooctl.yml,docker-compose.yml}` — single-stack multi-db, alongside the existing separate-stack example.

**UX principles to enforce:** every mutating command supports `--preview/--dry-run` (clone already does); destructive ops (`env destroy --purge`, `rollback --mode full`) require confirmation or `--yes`; errors name the exact failing check and the fix (doctor-style).

---

## 9. Safety model (consolidated)

**Already present (keep):** production cannot be a clone target; prod-source clone requires sanitization; clean-worktree gate for deploy + code rollback; prod backup-before-deploy; module-update/healthcheck failures fail the deploy; metadata trail; manifest checksums on restore.

**Added by this plan:**
- **Doctor preflight** in front of every mutating command (M1).
- **Temp-DB restore → sanitize → atomic swap** so a running Odoo never sees a half-restored or unsanitized DB; crons/queue disabled before the DB is visible (M3).
- **Swap guards:** never rename onto `production`; require successful connection-termination before swap (M3).
- **`env destroy` guards:** refuse `production`; `--purge` gated behind confirmation (M4).
- **Secret hygiene:** doctor warns on weak/common secrets; redaction precision avoids both leaking *and* over-redaction (M5).
- **Scheme correctness:** health/base-url use the real scheme, so we never silently probe HTTPS against an HTTP service (M2).
- **State integrity:** `.odooctl/` rooted at the project, so deploy history/rollback pointers can't be split across cwds (M1, fixes §0.1 #2).

---

## 10. Odoo 19-specific findings → concrete actions

Verified against `odoo:19.0` (`19.0-20260513`), PostgreSQL 17, 695 base modules:
- **`--without-demo=all` is deprecated** ("invalid boolean value: 'all', assume True"). → `odoo.without_demo: "True"`; init/update emit the version-correct flag (M2).
- **Bare `odoo -d …` inside the official image ignores the entrypoint `HOST/USER/PASSWORD`.** → always pass `--db_host/--db_user/--db_password` (M2). **The single most important Odoo-19 correctness fix.**
- **Filestore lives in the `/var/lib/odoo` volume** by default, not a host path. → `filestore_container_path` + named-volume filestore adapter (M3).
- **One Odoo service can serve multiple DBs** selected by `?db=`. → multi-db mode + healthcheck `db_param` (M3).
- **Live clone disturbs crons.** → temp-DB swap + disable crons before visibility (M3).
- **Sanitization is incomplete for real Odoo deployments.** Current SQL covers mail/fetchmail/cron/payment + config scrubbing, but **not** the OCA `queue_job` table or the `mail.mail` outbound spool. → add `disable_queue_jobs` + `purge_mail_queue`, guarded by `to_regclass(...) IS NOT NULL` so they no-op when the tables are absent (M3).
- Images `odoo:19` and `odoo:19.0` both exist; **pin `19.0`** for reproducibility (doc note).

---

## 11. Multi-db vs separate-stack (the explicit decision)

- **Separate-stack mode (default, production-grade):** each env = its own stack/domain; current uniqueness rules apply; full isolation. **Production must use this.**
- **Multi-db single-stack mode (dev/qa/staging convenience):** envs share `stack` + one Odoo service + one domain, differ by `db_name`, selected via `?db=`/`dbfilter`. The validator allows a shared `domain` **only here** (shared `stack` + `db_selector: true`).
- **Hard rule, enforced in validator + docs:** production never shares a `stack` with a non-prod env (cross-DB exposure risk). Default to separate-stack.

---

## 12. Risks & open questions

**Risks:**
- **R1 — Binary stream through `docker compose exec`.** Capturing `pg_dump -Fc` bytes reliably needs a binary-safe runner + `-T`. The text+redaction `run` would silently corrupt dumps **on the new path** (host mode is unaffected — it uses `-f`/file args). *Mitigation:* dedicated `run_capture_bytes`/`run_pipe_stdin` (M2) + a byte-integrity integration test; `docker compose cp` fallback.
- **R2 — Atomic DB swap needs zero connections.** `ALTER DATABASE … RENAME` fails with active sessions; Odoo + cron hold connections. *Mitigation:* `pg_terminate_backend` on the target, optionally pause Odoo or hide the DB via `dbfilter` during swap; never swap production targets (M3).
- **R3 — Named-volume filestore has no host path.** All filestore I/O must go through the container. *Mitigation:* container tar pipe + volume adapter; doctor distinguishes bind-mount vs volume (M3).
- **R4 — Multi-db cross-exposure.** Serving prod + non-prod from one Odoo risks cross-DB access. *Mitigation:* validator/docs enforce production never shares a stack; default separate-stack (M3/§11).
- **R5 — pipx omits system binaries.** Operators expect "install and go" but lack docker/pg tools. *Mitigation:* default container mode + doctor remediation hints + docs (M2/M5).
- **R6 — Refactor blast radius.** Threading `ProjectContext` + rooting state/paths touches every command **and several monkeypatched tests** (single-arg compose lambdas). *Mitigation:* M0 hardening first; M1 as a pure no-behavior-change refactor; update the affected monkeypatches in the same commit.
- **R7 — `status` DB-service bug is currently masking real failures.** Until M2, PostgreSQL always shows "unknown"; don't let monitoring trust that field before the fix.

**Open questions (decide before/within the noted milestone):**
- **Q1 (M2):** container backup — capture stdout to a host file, or dump-inside-then-`docker cp`? *Lean: stdout capture, cp fallback.*
- **Q2 (M3):** during swap, briefly stop Odoo or rely on connection-termination + `dbfilter`? *Lean: terminate + dbfilter; stop only if needed.*
- **Q3 (M4):** YAML round-trip for `env create` — `ruamel.yaml` (preserves comments, **new dep — not currently installed**) or re-emit via PyYAML (loses comments)? *Lean: ruamel behind the env-edit path only.*
- **Q4 (scope):** are non-prod stages ever on **different hosts** than production? If yes, we need a remote `ExecutionContext` (SSH/docker-context) — significant, currently out of scope. *Need a product call.*
- **Q5 (M2):** standardize required compose service names (`db`, `odoo`) or keep them fully configurable? *Lean: configurable with sane defaults, validated by doctor.*
- **Q6 (M3):** does sanitization need to cover Enterprise-only integrations (e.g. `iap.account`, document/sign webhooks) beyond the generic config scrub? *Defer until an Enterprise stack is in scope; keep the SQL-file hook as the escape valve.*

---

## 13. Recommended first 5 commits

Small, ordered, each green before the next. Cover M0 and the front of M1/M2.

1. **`test: isolate ODOO_DB_PASSWORD and register pytest markers`** — add `tests/conftest.py` (autouse env-isolation + shared dummies), `pyproject.toml` markers + `addopts = "-m 'not integration'"`. *(M0 — fixes gap #9; `pytest` passes with the var set or unset.)*
2. **`refactor: introduce ProjectContext and root all paths/state at repo`** — add `odooctl/context.py`; thread `project_dir`/`cwd=root` through compose + the `git` `run(...)` calls; root `MetadataStore`, `backups.local_path`, `sql_files`, `config_path`; update the single-arg `DockerComposeAdapter` monkeypatches and `test_deploy.py`. No behavior change beyond "respects project root." *(M1)*
3. **`feat(config): add execution_mode + container DB access + per-env scheme`** — extend `odooctl/config.py` (new optional fields + default-fill validator); update `examples/odooctl.yml` and `tests/test_config.py`. Backward compatible. *(M1/M2)*
4. **`feat: add odooctl doctor with preflight checks`** — add `odooctl/preflight.py` + `odooctl/commands/doctor.py` + `doctor` in `main.py`; Rich table + `--json`; `tests/test_doctor.py`. *(M1)*
5. **`feat(adapters): add Docker PostgreSQL backend + binary-safe runner`** — `run_capture_bytes`/`run_pipe_stdin` in `utils/shell.py`; `odooctl/adapters/db.py` with `make_db_adapter` + `DockerPostgresAdapter`; switch `backup.py`/`restore.py` to the factory; fix the `status` DB-service name; `tests/test_db_adapter.py`. *(M2)*

---

## 14. Migration path from current MVP

- **Config:** all v2 fields are optional with defaults → existing `odooctl.yml` loads unchanged. `execution_mode` defaults to `docker` for `docker_compose` runtime — **this changes backup/restore from host tools to container tools** for existing users. Make the default explicit in `init` output and `docs/configuration.md`; `execution_mode: host` preserves old behavior exactly. Emit a one-time `doctor` notice when `execution_mode` is unset.
- **State location changes (intended fix):** after M1, `.odooctl/` and `backups/` resolve under the **project root** instead of cwd. For anyone who ran the tool from a non-repo directory, document that they should move/recreate `.odooctl/` under the repo (it's gitignored and small; a fresh deploy re-seeds it). Note this in M1's changelog entry.
- **Commands:** existing signatures preserved; `-p/--project` and `-C/--project-dir` are additive (cwd remains the default). Running inside the repo continues to work after M1.
- **Tests:** M0/M1 changes are internal; external behavior preserved apart from the intended state-rooting fix.
- **No breaking CLI removals** across M0–M4. M5 adds `[s3]`-extra gating for real uploads (local-mirror fallback remains).

---

## 15. Appendix — command surface & verified bug list

### Command surface, before → after
| Area | Today | After this plan |
|---|---|---|
| Install | `uv pip install -e .` (dev) | `pipx install odooctl` / `uv tool install odooctl` |
| Project binding | implicit cwd | `project add/list/use/remove`, `-p <name>`, `-C <dir>` |
| Readiness | none | `odooctl doctor [--json] [--environment]` |
| Environments | hand-edit YAML + `clone` | `env list/create/destroy/show` |
| DB execution | host pg tools only | `execution_mode: docker | host` |
| Clone safety | restore into live DB | temp DB → sanitize → atomic swap |
| Multi-db | blocked by validator | `stack` + `db_selector` mode |
| Filestore | host path only | host path **or** named volume |
| Scheme | hardcoded HTTPS | per-env `scheme` |
| State location | cwd-relative `.odooctl/` (bug) | rooted at project repo |
| Scheduling | none | `schedule` → systemd timer / cron generator |
| S3 | local mirror stub | real S3 behind `[s3]` extra |

### Verified bugs to fix (independent of feature work)
1. `status.py` hardcodes DB service `"postgres"` → PostgreSQL status always "unknown" for `db`-named stacks. *(M2)*
2. `MetadataStore()`/`backups.local_path`/`sql_files`/`odoo.config_path` are cwd-relative → state/paths split by cwd. *(M1)*
3. `deploy._preflight` checks the compose path relative to the config dir, but execution runs compose in cwd → preflight can pass while execution targets the wrong/absent file. *(M1)*
4. `reverse_proxy.public_url` hardcodes HTTPS → wrong health/base URLs for HTTP stacks. *(M2)*
5. `update_modules_compose` passes no DB flags → fails on the official Odoo image. *(M2)*
6. Over-broad log redaction nukes common-word secrets (`odoo`). *(M5)*
7. Sanitization omits OCA `queue_job` + `mail.mail` spool. *(M3)*
8. `update_modules_local` is dead code — either wire it to a `host` execution mode or remove it. *(cleanup, M2)*

---

*End of plan. No code was changed by this document.*
