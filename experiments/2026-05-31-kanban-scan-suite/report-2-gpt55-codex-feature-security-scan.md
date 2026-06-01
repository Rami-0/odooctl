# odooctl — Independent GPT-5.5 Codex Feature/Security Audit

Date: 2026-06-01T08:34:32Z
Repository: /home/dev/odooctl
Branch inspected: master
Commit inspected: 30d29b0c79be3f705aa39b81178555222f2356d5
Working tree at audit start: clean; branch was ahead of origin/master by 1 commit
Audit mode: report-only; no product code was changed
Report path: /home/dev/odooctl/experiments/2026-05-31-kanban-scan-suite/report-2-gpt55-codex-feature-security-scan.md

## Codex execution path

The task requested a connected OpenAI Codex substantive scan with high reasoning. I first tried the standalone Codex CLI path from the repo:

- `codex` was not installed in PATH.
- `npx -y @openai/codex --version` worked and reported `codex-cli 0.135.0`.
- A connectivity probe with `npx -y @openai/codex exec --cd /home/dev/odooctl -s read-only -c model_reasoning_effort='"high"' ...` selected `model: gpt-5.5`, `provider: openai`, `reasoning effort: high`, but failed with HTTP 401 because no standalone CLI bearer/basic auth was available.
- Per the task's fallback rule, the substantive audit continued through the connected Hermes OpenAI Codex provider path for this session (`provider: openai-codex`, `model: gpt-5.5`). A separate Codex-provider delegated breadth scan was attempted but timed out without a usable summary, so the findings below are limited to issues I independently verified against the source and focused commands.

No real credentials were printed or preserved. Canary values used in verification are described only as `[REDACTED]`.

## Commands and verification performed

Orientation and tool checks:

- `pwd; git rev-parse --show-toplevel; git status --short --branch; git rev-parse HEAD`
  - repo: `/home/dev/odooctl`
  - branch/status: `master...origin/master [ahead 1]`
  - commit: `30d29b0c79be3f705aa39b81178555222f2356d5`
- `command -v codex; codex --version` — no installed `codex` binary.
- `npx -y @openai/codex --version` — `codex-cli 0.135.0`.
- `npx -y @openai/codex exec ...` — gpt-5.5/high selected, then 401 Unauthorized due missing standalone CLI auth.

Source/security inspection:

- Read and reviewed security-sensitive paths under `odooctl/`: `config.py`, `context.py`, `main.py`, `api/auth.py`, `api/app.py`, `api/routes_operations.py`, `api/queue.py`, `runner/worker.py`, `operations/*`, `security/*`, `utils/shell.py`, `adapters/db.py`, `adapters/filestore.py`, `adapters/docker_compose.py`, `domains/traefik.py`, `services/{backup,restore,clone,deploy,promote}.py`, `odoo/{db_swap,module_update}.py`, and relevant CLI command wrappers.
- Searched for shell/command sinks: `sh -lc`, `shell=True`, `os.system`, `subprocess`, `eval`, `exec`, and secret/token/password handling.
- Ran focused proof scripts for command-argument secret leakage, shell-string injection construction, Traefik rule injection, and config validator behavior.
- Ran focused tests:
  - `python -m pytest tests/test_security.py tests/test_api.py tests/test_filestore_volume.py tests/test_config.py -q` -> `166 passed in 1.41s`.
  - `python -m pytest tests/test_clone.py tests/test_restore.py tests/test_promote.py -q` -> `46 passed, 2 failed`; both failures reproduce the `--project-dir` handling bug described in F6.

## Executive summary

The repository has a mature security shape for a single-host Odoo control plane: API auth requires a token, capability tokens use HMAC with expiry and runner-side nonce consumption, the API/runner split is clear, importer detection is read-only, most subprocess usage is list-argument based, and recent restore-to-env logic correctly uses `cfg.is_protected()` for protected source/target checks.

The verified concerns cluster into six concrete areas:

1. Docker-mode clone/filestore code still builds `sh -lc` strings from unvalidated config identifiers. This is the highest-risk finding if project config can be influenced by a less-trusted actor than the runner/operator.
2. The codebase defines a generalized `is_protected()` policy, but several destructive paths still check only the literal environment name `"production"`.
3. Full restore/db-swap/deploy failure flows can destroy or mutate live state before health verification, with incomplete rollback behavior.
4. Odoo DB passwords are placed in process argv and can leak through `CommandError` messages.
5. Traefik dynamic rules interpolate raw domain strings into `Host(...)` expressions.
6. Global `--project-dir` is ignored by at least the top-level `promote` wrapper; the current test suite already catches this with two failing tests.

## Prioritized findings

### F1 — High — Docker-mode shell command injection from unvalidated DB/filestore identifiers

Affected paths:

- `odooctl/adapters/db.py:121-124`
- `odooctl/adapters/filestore.py:94-115`
- Root input model: `odooctl/config.py:24-40`, `44-62`, `78-87`, `151-231`
- Reachability: `odooctl/services/clone.py:66-88`, `odooctl/services/restore.py:112-125`, `136-145`

Evidence:

`DockerPostgresAdapter.clone_db_in_container()` builds a shell script by interpolating `src`, `dst`, `internal_host`, and `service_user`:

```python
# odooctl/adapters/db.py:121-124
def clone_db_in_container(self, src: str, dst: str) -> None:
    self.drop_create(dst)
    script = f"pg_dump -Fc -h {self.config.internal_host} -U {self.config.service_user} -d {src} | pg_restore -h {self.config.internal_host} -U {self.config.service_user} -d {dst}"
    run(self._cmd("sh", "-lc", script), cwd=self.project_dir, env=self._password_env(), stream=True)
```

`DockerVolumeFilestore` does the same for filestore restore/copy:

```python
# odooctl/adapters/filestore.py:94-115
name = self._relative_name(target_path)
parent = f"{self.root}/filestore"
self.compose.exec(self.service, ["sh", "-lc", f"mkdir -p {parent!s} && rm -rf {parent}/{name}"], stream=True)
...
self.compose.exec(self.service, ["sh", "-lc", f"mkdir -p {self.root}/filestore && rm -rf {dst} && cp -a {src} {dst}"], stream=True)
```

The config model accepts raw strings for `domain`, `db_name`, `filestore_path`, `filestore_volume`, `postgres.internal_host`, `postgres.service_user`, and `odoo.filestore_container_path`. `validate_environment_graph()` checks uniqueness and environment graph consistency, but not identifier charset or shell-safety. A focused validation proof showed:

```text
malicious_config_validation_succeeded= True
raw_domain_preserved= True
raw_filestore_preserved= True
```

A capture-only proof, without invoking Docker or Postgres, confirmed that injected shell markers survive into the `sh -lc` script:

```text
db_clone_shell_marker_present= True
db_clone_uses_shell= True
filestore_shell_marker_present= True
filestore_uses_shell= True
```

Impact:

- In Docker execution mode, malicious `db_name` / `filestore_path` / related config values can execute arbitrary shell syntax inside the Postgres or Odoo service container when clone/restore paths run.
- Under a strictly trusted local-operator model, this is a dangerous foot-gun and container boundary break.
- Under a future API/runner or multi-project model where repo config can be influenced by a lower-trust party, it becomes a runner privilege-escalation risk.

Remediation:

- Add strict validators for DB names, environment names, filestore names, Docker service names, and container-relative roots. Prefer allowlists such as PostgreSQL identifier-safe strings (`^[A-Za-z_][A-Za-z0-9_]{0,62}$`) for DB identifiers and a separate safe path-segment validator for volume filestore names.
- Remove the shell strings. Use list-argument subprocesses and pipe `pg_dump` to `pg_restore` in Python, or quote every interpolated value with `shlex.quote()` as a temporary defense.
- Add regression tests with `;`, `$()`, backticks, whitespace, and newlines in rejected config fields.

### F2 — High — Protected-environment policy bypass via literal `"production"` checks

Affected paths:

- `odooctl/config.py:233-237` defines the broader policy.
- Literal-only guards remain in:
  - `odooctl/services/deploy.py:72-75`, `101-108`
  - `odooctl/services/clone.py:40-42`
  - `odooctl/odoo/db_swap.py:52-58`
  - `odooctl/config.py:172-177`
  - `odooctl/commands/env.py:279-314`

Evidence:

The policy function is broad:

```python
# odooctl/config.py:233-237
def is_protected(self, name: str) -> bool:
    env = self.env(name)
    if env.protected is not None:
        return env.protected
    return name == "production" or env.tier == "production"
```

A proof config with `live: {tier: production}` produced:

```text
live_is_protected= True
live_name_equals_production= False
```

But deploy/clone/db-swap/env-destroy use literal checks. Examples:

```python
# odooctl/services/deploy.py:72-75
if environment == "production":
    print("[deploy] backup")
    backup_result = backup_execute(ctx, environment)
```

```python
# odooctl/services/clone.py:40-42
should_sanitize = dst.sanitize if sanitize is None else sanitize
if source == "production" and not should_sanitize:
    raise RuntimeError("Refusing to clone production data without sanitization enabled")
```

```python
# odooctl/odoo/db_swap.py:52-58
if target_env_name == "production":
    raise RuntimeError("Refusing to swap a temporary database into the production environment")
...
drop_database(pg, target_db, maintenance_db=maintenance_db)
rename_database(pg, temp_db, target_db, maintenance_db=maintenance_db)
```

Impact:

An environment named `live`, `prod`, or `prod-eu` with `tier: production` or `protected: true` is protected according to the config model but can miss destructive safety behavior:

- no pre-deploy backup in `run_deploy()`;
- no production-source sanitization refusal in `run_clone()`;
- no db-swap guard in `swap_temp_database()`;
- no config-time prevention from becoming a clone target;
- no protection from `env destroy --purge`, which calls `db.drop()` and `fs.delete()`.

Remediation:

- Replace literal `environment == "production"` / `target_env_name == "production"` checks with `cfg.is_protected(name)` in every destructive path.
- Where helper functions do not currently receive config, pass a policy callback or a precomputed `target_is_protected` boolean.
- Add regression tests for `tier: production` and `protected: true` environments not named `production`.

### F3 — High — Full restore/db-swap/deploy failure flows can mutate or destroy live state before verification

Affected paths:

- `odooctl/services/restore.py:136-152`
- `odooctl/adapters/db.py:76-85`, `93-106`
- `odooctl/odoo/db_swap.py:56-58`
- `odooctl/services/deploy.py:71-108`

Evidence:

The safer cross-environment restore path now restores into a temp DB and refuses protected targets (`restore.py:91-125`). However, the same-environment full restore path still restores directly into the live DB:

```python
# odooctl/services/restore.py:136-145
def run_restore(ctx: ServiceContext, environment: str, backup: str = "latest") -> RestoreResult:
    cfg = ctx.project.config
    env = cfg.env(environment)
    backup_dir = resolve_backup_dir(environment, backup, ctx.project.backups_dir)
    validate_backup_dir(...)
    pg = make_context_db_adapter(ctx.project) if cfg.runtime.execution_mode == "docker" else PostgresAdapter(cfg.postgres)
    pg.restore(env.db_name, backup_dir / "db.dump")
    ...
    fs.restore_archive(backup_dir / "filestore.tar", target_filestore)
```

For the Docker adapter, `restore()` calls `drop_create()` before `pg_restore`:

```python
# odooctl/adapters/db.py:76-85, 93-106
def restore(self, db_name: str, dump_path: str | Path) -> None:
    self.drop_create(db_name)
    run_pipe_stdin(... "pg_restore" ...)
...
run(... "dropdb" ... db_name, "--if-exists" ...)
run(... "createdb" ... db_name ...)
```

`swap_temp_database()` drops the target before renaming the temp database:

```python
# odooctl/odoo/db_swap.py:56-58
terminate_connections(pg, target_db, maintenance_db=maintenance_db)
drop_database(pg, target_db, maintenance_db=maintenance_db)
rename_database(pg, temp_db, target_db, maintenance_db=maintenance_db)
```

Deploy takes a backup only for the literal `production` name, mutates the live DB through module updates, and on failure only restarts the container:

```python
# odooctl/services/deploy.py:82-108
update_modules_compose(...)
check_url(...)
...
except Exception as exc:
    message = str(exc)
    if environment == "production":
        try:
            compose.restart(cfg.odoo.service)
```

Impact:

- A corrupt dump, disk-full condition, killed process, or failed `pg_restore` after `drop_create()` can leave the target database empty or absent.
- `swap_temp_database()` creates a no-target-DB window between drop and rename; a crash or reconnect race can strand the environment.
- A failed production deploy after module migration has only a restart fallback; the just-created backup is recorded but not restored.

Remediation:

- Apply the temp-restore + verify + swap model to full restore as well, not only cross-environment restore.
- Implement db swap as rename-old-aside -> rename-temp-to-target -> healthcheck -> drop old. On failure, attempt rename-old-back.
- Set target DB `ALLOW_CONNECTIONS false` before termination/drop/rename where PostgreSQL permits it.
- On protected deploy failure, restore or promote from the backup taken before mutation, or run module updates against a temp DB before swapping.

### F4 — Medium — Odoo DB password is put on argv and leaks through unredacted `CommandError`

Affected paths:

- `odooctl/odoo/module_update.py:24-28`, `51-62`
- `odooctl/adapters/docker_compose.py:38-39`
- `odooctl/utils/shell.py:20-23`, `43-61`

Evidence:

`build_update_modules_args()` reads the secret from an env var, then appends the raw value to argv:

```python
# odooctl/odoo/module_update.py:24-28
if db_password_env:
    value = os.getenv(db_password_env)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {db_password_env}")
    args.extend(["--db_password", value])
```

`CommandError` formats raw args without calling the redactor:

```python
# odooctl/utils/shell.py:20-23
class CommandError(RuntimeError):
    def __init__(self, result: CommandResult):
        super().__init__(f"Command failed ({result.returncode}): {' '.join(result.args)}\n{result.stderr}")
```

Focused verification with a temporary canary value, not printed here, showed:

```text
argv_secret_leak_verified= True
argv_secret_arg_index= 6
```

Impact:

- Any local process observer can see the password in process argv while Odoo/docker-compose exec is running.
- If the command fails, the raw value is embedded in the Python exception string. That error can propagate into operation status/error surfaces and logs.
- The existing output redaction only scrubs stdout/stderr against environment values; it does not scrub `result.args` before formatting the exception.

Remediation:

- Do not pass DB passwords on argv. Prefer an env var inside the container, an Odoo config file mounted with correct permissions, or stdin/file descriptor depending on Odoo support.
- Redact command args before storing or formatting `CommandResult`/`CommandError`.
- Add a regression test asserting a canary secret is absent from `str(CommandError(...))`, operation errors, and streamed API events.

### F5 — Medium — Traefik Host rule injection from raw domain strings

Affected paths:

- `odooctl/domains/traefik.py:26-55`
- `odooctl/services/domain.py:36-52`
- `odooctl/commands/domain.py:21-30`
- Root input: `odooctl/config.py:30`

Evidence:

`TraefikAdapter.attach_route()` inserts `spec.domain` directly into a Traefik rule expression:

```python
# odooctl/domains/traefik.py:34-40
router: dict = {
    "rule": f"Host(`{spec.domain}`)",
    "service": service_name,
    "entryPoints": ["websecure" if spec.scheme == "https" else "web"],
}
```

`DomainService.attach()` accepts a raw `domain` string from the CLI and persists it to config:

```python
# odooctl/services/domain.py:36-52
spec = RouteSpec(domain=domain, environment=environment, scheme=env.scheme, port=env.port)
self._adapter.attach_route(spec)
...
raw.setdefault("environments", {})[environment]["domain"] = domain
```

A temp-dir proof with a crafted domain containing backticks and a second Traefik matcher produced:

```text
traefik_rule_injection_marker_present= True
traefik_rule_contains_raw_backtick= True
```

Impact:

- A malformed/malicious domain can alter the Traefik rule expression, potentially broadening route matches or routing unintended hosts/paths to an Odoo service.
- This is config/operator-input driven, not unauthenticated remote execution. It becomes more important if domain attachment is exposed through API workflows or if config changes are accepted from PRs.

Remediation:

- Validate domains as FQDN/IDNA hostnames before route generation and config persistence.
- Reject backticks, parentheses, whitespace, slashes, commas, logical operators, and URL schemes in `EnvironmentConfig.domain` and `domain attach`.
- Add tests that a domain containing backticks or `PathPrefix` is rejected.

### F6 — Medium — Global `--project-dir` context is ignored by `promote`; existing tests fail

Affected paths:

- `odooctl/main.py:54-63`, `66-73`, `135-143`
- `odooctl/registry.py:109-125`
- `tests/test_promote.py:516-557`

Evidence:

The top-level callback stores global project context:

```python
# odooctl/main.py:66-73
def main(ctx: typer.Context, ..., project_dir: Path | None = typer.Option(None, "--project-dir", "-C", ...)):
    ctx.obj = {"project": project, "project_dir": project_dir}
```

Command wrappers then call `_context_config(config)`, which tries to recover the root Click context:

```python
# odooctl/main.py:54-63
ctx = click.get_current_context(silent=True)
root = ctx.find_root() if ctx is not None else None
obj = root.obj if root is not None and isinstance(root.obj, dict) else {}
project = obj.get("project")
project_dir = obj.get("project_dir")
if not project and project_dir is None:
    return config
```

A minimal Typer-runner proof monkeypatched `promote_cmd.execute()` to print the config path passed by the wrapper. Invoked with `--project-dir <tmp>`, it printed:

```text
CONFIG_ARG=odooctl.yml
captured_config_exists= False
```

The real test subset reproduces the bug:

```text
python -m pytest tests/test_clone.py tests/test_restore.py tests/test_promote.py -q
...
2 failed, 46 passed
FAILED tests/test_promote.py::test_cli_promote_requires_yes_for_protected_target
FAILED tests/test_promote.py::test_cli_promote_yes_flag_bypasses_protection
```

Both failures show `Config file not found: /home/dev/odooctl/odooctl.yml`, even though the test passed `--project-dir <tmp_path>` containing its own `odooctl.yml`.

Impact:

- CLI users running from outside a project root can unintentionally operate against the current working directory or fail instead of using `--project-dir`.
- For destructive commands, context confusion is a safety issue: a caller believes they are targeting one project while config resolution ignores that selection.

Remediation:

- Stop relying on `click.get_current_context()` inside wrappers. Pass the Typer context into commands explicitly or use a shared context object dependency that is proven by tests.
- Add a regression matrix for every top-level command that accepts `config`, using `--project-dir` from a different cwd.
- Audit sub-typers such as `domain`, `env`, `project`, and `ops` for the same global-context behavior.

## Positive controls observed

- `odooctl serve` refuses to start without `--api-key` or `ODOOCTL_API_KEY` (`commands/serve.py:38-43`) and binds to `127.0.0.1` by default (`commands/serve.py:22-24`).
- Capability tokens are HMAC-signed with expiry and constant-time signature comparison (`security/tokens.py:128-167`).
- Runner-side token verification checks action, environment, and project scope (`runner/worker.py:135-143`) and consumes nonces (`runner/worker.py:63-91`, `163-171`).
- The API dependency maps token roles to RBAC roles and rejects missing/invalid bearer tokens (`api/auth.py:20-69`).
- The newer cross-environment restore path uses `cfg.is_protected()` and refuses protected-target restores and unsanitized protected-source restores (`services/restore.py:91-125`).
- Import detection documents and implements a read-only path based on `yaml.safe_load`, not Docker/subprocess access.
- Focused security/API/config/filestore tests passed: `166 passed in 1.41s`.

## Open questions

1. Is `odooctl.yml` considered fully trusted operator-owned input, or can it be changed through PRs, generated imports, user forms, or API-managed projects? F1/F5/F8 severity depends heavily on that trust boundary.
2. Should `restore <environment>` be allowed against protected environments without an explicit `--yes`/break-glass flag? Current `restore_to_env()` is protective; same-env full restore is not.
3. Is the branch being ahead of `origin/master` intentional for this audit baseline? I inspected the live working repo at commit `30d29b0c79be3f705aa39b81178555222f2356d5`.
4. Should the current `--project-dir` regression block release readiness? The failing tests suggest yes for CLI reliability and destructive-operation safety.

## Recommended remediation order

1. Fix identifier/domain validation and remove or quote the three `sh -lc` sites (F1, F5).
2. Replace literal `"production"` checks with `cfg.is_protected()` throughout destructive paths (F2).
3. Rework full restore/db-swap/deploy failure behavior so live state is not destroyed before verification and protected deploy failures use the backup they create (F3).
4. Remove DB passwords from argv and redact command args in errors/events/logs (F4).
5. Fix `_context_config()`/`--project-dir` propagation and restore the failing promote tests (F6).

## Final status

Audit completed via connected OpenAI Codex provider fallback after standalone Codex CLI auth failed. Six verified findings are documented above; no product code was modified.
