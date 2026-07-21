# Changelog

All notable changes to `odooctl` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **License changed from MIT to AGPL-3.0-or-later** with a commercial
  license available for proprietary embedding/resale — see `LICENSING.md`.
  (No prior release was distributed under MIT.)
- Contributions now require a Developer Certificate of Origin sign-off
  (`git commit -s`) plus a commercial-relicensing grant; see
  `CONTRIBUTING.md`.

### Added

- **User accounts and browser sessions.** Persistent server-level accounts
  (`odooctl user add/list/role/passwd/disable/enable/remove`; salted scrypt
  password hashing, scheme-prefixed for future argon2/OIDC providers) with
  email/password login for the web UI (`POST /auth/login`, HttpOnly
  SameSite=Lax cookie, per-email login throttling). Sessions are revocable —
  logout, `user disable`, and password changes kill live sessions
  immediately — and roles are re-read from the user store on every request.
  Bearer HMAC tokens remain the CLI/CI credential. Admins manage accounts
  from the UI (Access page) or `/users` API with a role ceiling (never above
  your own role), outrank guards, and no self-disable/delete.
- **Ownership.** Projects (`odooctl project add --owner`, `odooctl project
  owner`, `PATCH /projects/{p}/owner`) and environments (`owner:` in
  `odooctl.yml`) record an owning user/team, shown in listings, the API,
  and the UI.
- **Real actor attribution.** Operations and audit records now carry the
  acting principal: the authenticated user's email via the API/UI, and
  `local:<os-user>` (overridable with `ODOOCTL_ACTOR`) instead of a `"cli"`
  literal for CLI commands.
- New RBAC action `users` (admin+) gating account management and ownership
  changes; a regression test asserts every mutating API route requires an
  authenticated principal.
- **Machine-local config overlay (`odooctl.local.yml`).** An untracked
  sibling of `odooctl.yml`, deep-merged over it by every command, for
  machine-specific values (ports, resource limits, TLS off, local paths).
  Precedence: env vars > `odooctl.local.yml` > `odooctl.yml`; mappings merge
  key-by-key, scalars and lists replace. A custom `--config custom.yml`
  merges `custom.local.yml`. `odooctl init`/`odooctl setup` gitignore the
  overlay automatically, and `odooctl validate` reports the merged overlay
  and warns when it is not gitignored (an unignored overlay would block
  `odooctl sync` with `dirty_worktree`).
- **`odooctl sync <env>` — pull-based auto-deploy.** Fetches the remote,
  compares the last deployed commit against the remote tip of the
  environment's branch, and runs the existing deploy pipeline (pre-deploy
  backup, health check, rollback path) when the environment is behind and
  `auto_deploy: true` (previously a dead config flag). All other states are
  explicit no-ops; attention states (diverged history, missing remote,
  fetch failure) exit non-zero so timers surface them. `--force` overrides
  the `auto_deploy` gate; `--json` emits machine-readable output.
- `odooctl schedule sync --env <env>` renders a systemd timer or cron entry
  for the sync poller (default interval: every 5 minutes).
- The generated GitHub Actions workflow now targets a self-hosted runner and
  documents that pull-based `odooctl sync` is the primary CI/CD model
  (GitHub-hosted runners cannot reach a VPS Docker daemon).
- Open-source contribution infrastructure: label taxonomy
  (`.github/labels.yml`) with automated sync, path-based PR auto-labeling,
  issue triage flow (`status/needs-triage`), a documentation issue
  template, issue-form contact links, `SUPPORT.md`, and GitHub Discussions.

## [0.3.0] - 2026-07-20

Reliability and usability pass from a live local install/test run
(`experiments/2026-07-20-pypi-install-test-suite/`).

### Fixed

- **`clone`/`restore` no longer fail on the final database swap when
  `db_selector: true`.** Odoo's database-selector auto-connects to every
  visible database, including the transient `<db>_incoming` one, which made
  `ALTER DATABASE … RENAME` fail with "database is being accessed by other
  users". The swap now terminates sessions on the incoming database
  immediately before promoting it (both the rename-aside and legacy paths).

### Added

- **`odooctl serve --allowed-host` / `--trusted-host` (and
  `ODOOCTL_ALLOWED_HOSTS`)** to reach the API by IP or hostname (LAN,
  Tailscale, …) without a reverse proxy. The API stays localhost-only by
  default; these values are *appended*, never replacing the lockdown. Binding
  to a non-loopback host without any allowed host now prints a clear warning
  instead of silently rejecting every request with "Invalid host header".
- **Runner liveness in the web UI and API.** The privileged runner now writes
  a heartbeat; a new `GET /runner/status` endpoint reports whether operations
  are actually being processed. The dashboard shows a runner online/offline
  pill and, when offline, explains that queued work will not run until you
  start `odooctl runner` — instead of leaving the queue looking broken.
- **Web UI: cancel queued operations, a refresh control, and token-expiry
  display.** Queued operations gain a Cancel action (wired to
  `POST /operations/{id}/cancel`).
- **Live container visibility and control from the web UI.** The runner
  probes `docker compose ps` every 10 s and writes a per-project snapshot;
  `GET /projects/{p}/containers` serves it (the API never touches Docker).
  The dashboard gains a Containers panel (project page + a per-environment
  tab) showing service state/health/uptime/image with staleness detection,
  plus per-service **Logs** (new `service_logs` operation kind, viewer-
  allowed, redacted tail streamed over SSE) and **Restart** (new
  `service_restart` kind, operator+; requires admin when *any* environment in
  the project is protected, since compose services are shared across
  environments — a new project-wide protection rule, `rbac.kind_protected`).
  Service names are validated against the configured odoo/postgres services.
- **Access management page in the web UI.** `#/access` renders the full
  role → action RBAC matrix (`GET /rbac/matrix`) with the caller's roles
  highlighted and the protected-environment floor explained, and lets admins
  issue scoped bearer tokens from the browser (`POST /tokens`): role capped
  at the minter's own rank, TTL capped at 7 days, token shown once and never
  stored.

## [0.2.0] - 2026-07-19

Production-hardening pass driven by the 2026-05-31 security audits
(reports 1–4 in `experiments/2026-05-31-kanban-scan-suite/`).

### Security

- Removed all `sh -lc` command composition: filestore operations use
  list-argv execs and DB cloning pipes `pg_dump` into `pg_restore` through a
  new no-shell `run_pipe()` helper. A guard test keeps shell sinks out.
- Config-boundary validation: environment/db/service/volume names must match
  a strict identifier rule; domains must be valid DNS hostnames (normalized
  to lowercase) and are re-validated when Traefik rules are built.
- Every protected-environment policy check goes through `is_protected()`
  (name `production` or `tier: production`); literal name comparisons are
  gone and a guard test keeps them out.
- Database passwords never appear on process argv (passed via
  `docker compose exec -e PGPASSWORD` name-only injection); command errors,
  operation-store errors, and streamed events are redacted.
- Sanitization now also covers the legacy `payment_acquirer` table, freezes
  `web.base.url`, clears OAuth client secrets and IAP tokens, and deletes
  Odoo 19 `auth_passkey` WebAuthn credentials; crons are disabled under
  every profile including `minimal`.
- Capability tokens default to a 300 s TTL; consumed-nonce records are
  purged after 2 h; `ODOOCTL_API_KEY` must be at least 32 characters.
- Operation cancel is a write action (viewers get 403) and `/operations/*`
  endpoints enforce the token's project scope.
- Audit chains can be HMAC-keyed via `ODOOCTL_AUDIT_KEY`, making
  truncate-and-rehash tampering detectable.
- Path containment for backup ids, registry config paths, project names,
  migration report paths, and `import --output` (new `--allow-outside`).
- `security token mint`/`verify` sign with `ODOOCTL_API_KEY` by default —
  the key the API and runner actually verify with.

### Safety

- `restore` restores into a temporary database and swaps only after
  `pg_restore` succeeds (verify-before-destroy), for both same-environment
  and cross-environment restores.
- A failed protected-environment deploy automatically restores its own
  pre-deploy backup when the database may have been mutated, and records
  the recovery outcome in deployment metadata.
- `restore` and `rollback --mode full` require `--yes` or interactive
  confirmation.
- Health checks require HTTP 2xx and treat redirects as unhealthy; the
  default health path is now `/web/health` (Odoo 15+).
- `runner --once` exits non-zero when the processed operation failed;
  `runner --fail-fast` stops the loop on the first failure.

### Added

- GitHub Actions CI (ruff, pytest on Python 3.11–3.13 with a coverage
  floor, package build + wheel smoke test) and a tag-driven release
  workflow using PyPI trusted publishing.
- Real-Odoo integration harness (`tests/integration/`): disposable Docker
  stacks per Odoo version covering the full operator lifecycle, including
  API-enqueue → runner execution parity.
- `--project`/`--project-dir` regression matrix across every config-taking
  command; the selector is threaded explicitly through `typer.Context`.
- Shell completion; web UI empty states, running-operation indicator, and
  role-aware Migrate gating; MkDocs documentation site configuration.

### Changed

- `click` is a direct dependency (typer ≥ 0.27 no longer provides it).
- The default healthcheck path changed from `/web/login` to `/web/health`.

## [0.1.0] - 2026-05-30

Initial public release of `odooctl`, a CLI-first, Odoo-aware deployment
platform for self-hosted Odoo projects using Docker Compose.

This release closes the v-next milestones M0 through M5 and ships the MVP
foundation: Docker-native database and filestore operations, project and
environment management, scheduled operation generation, install metadata,
secret redaction, optional real S3 uploads, documentation, and tests.

### Added

- **M0 — Test-harness hygiene.** Pytest environment isolation and
  registered `unit`, `integration`, and `docker` markers so the default
  suite runs without Docker or live infrastructure.
- **M1 — Project context and `doctor`.** `ProjectContext` resolves all
  paths relative to the configuration root, and a new `odooctl doctor`
  command runs side-effect-free preflight checks with human and JSON
  output. Context is threaded through deploy, backup, clone, restore,
  rollback, status, logs, update-modules, and validate.
- **M2 — Docker execution mode.** Additive `runtime.execution_mode` and
  container PostgreSQL/Odoo configuration fields. New host and Docker
  PostgreSQL adapters, binary-safe command helpers, Docker Compose byte
  stream helpers, and an adapter factory. Module updates build official
  image-safe Odoo invocations with `-c`, `--db_host`, `--db_user`, and
  `--db_password` from config and environment.
- **M3 — Safer clone and Docker filestores.** Clone restores into a
  temporary database, sanitizes it before exposure, then terminates target
  connections, drops the old target, and renames into place. Named-volume
  filestore adapter for Docker, with archive/restore/copy command
  construction and same-stack `db_selector` validation.
- **M4 — Project and environment registry.** XDG-backed global project
  registry with `odooctl project add/list/use/remove/current`, plus global
  `-p/--project` and `-C/--project-dir` resolution. Environment lifecycle
  commands: `odooctl env list/show/create/destroy`, including a guarded
  env purge.
- **M5 — Productization.** PyPI/pipx install metadata, scheduled
  operation generation (`odooctl schedule backup`, `odooctl schedule
  doctor`), precise secret redaction with configurable
  `redaction.min_secret_length` and `redaction.ignore_values`, an optional
  real S3 adapter behind the `s3` extra, expanded documentation under
  `docs/`, runnable examples under `examples/`, and broader test
  coverage.

### Security

- Secrets are referenced via environment variables and `*_env` config
  fields and are never stored in the repository or in checked-in
  configuration.
- Logs redact environment values whose variable names look secret-bearing
  (`PASSWORD`, `SECRET`, `TOKEN`, `KEY`, `PASSWD`); the redaction policy
  is configurable.
- `odooctl doctor` warns when referenced secrets are shorter than the
  configured minimum or fall on the redaction ignore list.

[Unreleased]: https://github.com/odooctl/odooctl/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/odooctl/odooctl/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/odooctl/odooctl/releases/tag/v0.1.0
