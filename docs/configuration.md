# Configuration

Run `odooctl init` to create `odooctl.yml`.

Guidelines:

- Keep secrets out of YAML.
- Use `password_env` and provider-specific environment variable references.
- Define both `production` and at least one non-production environment so clone/deploy flows stay explicit.
- Point `staging.clone_from` at the source environment you want to clone.
- Prefer Docker execution mode for Docker Compose stacks where PostgreSQL is not exposed on the host.

Key sections:

- `project`: project name and Odoo version.
- `runtime`: Docker Compose file, reverse-proxy mode, and `execution_mode` (`docker` or `host`).
- `environments`: per-environment branch, scheme/domain/port, database, filestore, clone source, sanitization flag, `db_selector`, module update list, `auto_deploy` (opt-in for pull-based [git sync](git-sync.md)), and an optional `owner` (owning user/team label, see [Users & access](users-and-access.md)).
- `postgres`: host-side connection settings plus Docker service/internal-host settings for container-native operations.
- `odoo`: image, config path, addons paths, service name, DB flags for module updates, and container filestore root.
- `backups`: local backup path, optional S3 remote storage, and retention policy.
- `sanitization`: SQL files and built-in staging safety toggles.
- `healthcheck`: path and retry timing used after clone/deploy/restore operations.
- `redaction`: log-redaction policy for sensitive environment values.

## Machine-local overlay (`odooctl.local.yml`)

`odooctl.yml` lives in the git repo and is shared by every machine that checks
the project out. For machine-specific values — ports, resource limits, TLS off,
local paths — create an untracked `odooctl.local.yml` next to it. When present,
it is deep-merged over the main config by every command.

Precedence (highest wins):

1. Environment variables — the `*_env` indirections (`password_env`, S3
   credential envs, …) are read at runtime and always take effect.
2. `odooctl.local.yml` — machine-local overrides.
3. `odooctl.yml` — the shared project config.

Merge semantics: mappings merge key-by-key, so you only write the keys you
change; scalars and **lists replace wholesale** (an overlay `update_modules`
replaces the main list, it does not append). Example for a laptop running the
stack over plain HTTP:

```yaml
# odooctl.local.yml — gitignored, never committed
environments:
  production:
    scheme: http
    port: 8069
```

Rules:

- **Gitignore it.** `odooctl init` and `odooctl setup` add `odooctl.local.yml`
  to `.gitignore` automatically. An untracked-but-not-ignored overlay blocks
  `odooctl sync` with `dirty_worktree`; a committed one is no longer
  machine-local. `odooctl validate` warns when the overlay is not ignored.
- A custom config name gets a matching overlay: `--config custom.yml` merges
  `custom.local.yml`.
- `odooctl validate` prints which overlay was merged; config-writing commands
  (`env add`, domain attach, …) always write the shared `odooctl.yml`, never
  the overlay.

## Docker vs host execution

`runtime.execution_mode: docker` runs PostgreSQL operations through the configured Compose DB service. Use this for the common topology where the DB service is named `db` and port `5432` is not published to the host:

```yaml
runtime:
  type: docker_compose
  compose_file: docker-compose.yml
  execution_mode: docker
postgres:
  user: odoo
  password_env: ODOO_DB_PASSWORD
  service: db
  internal_host: db
```

`runtime.execution_mode: host` keeps the older behavior: `psql`, `pg_dump`, and `pg_restore` run on the operator host and connect to `postgres.host:postgres.port`.

## Multi-db local staging

For local/shared-stack experiments, two environments may share the same `domain` only when both use the same `stack` and set `db_selector: true`. Health checks then append `?db=<db_name>`.

```yaml
environments:
  production:
    stack: local
    scheme: http
    domain: localhost
    port: 18069
    db_selector: true
    db_name: odoo_prod
  staging:
    stack: local
    scheme: http
    domain: localhost
    port: 18069
    db_selector: true
    clone_from: production
    sanitize: true
    db_name: odoo_staging
```

Keep production isolation stricter for real routed deployments.

## S3 remote backups

Install the optional extra when you want real S3 uploads:

```bash
pipx install 'odooctl[s3]'
# or
uv tool install 'odooctl[s3]'
```

Configure a bucket and optional prefix/region/endpoint. Credentials can come from AWS defaults or the configured env vars:

```yaml
backups:
  remote:
    type: s3
    bucket: acme-odoo-backups
    prefix: acme/production
    region: eu-central-1
    endpoint_env: ODOO_S3_ENDPOINT
    access_key_env: ODOO_S3_ACCESS_KEY
    secret_key_env: ODOO_S3_SECRET_KEY
```

If `boto3` or credentials are unavailable, `odooctl` warns and mirrors the remote backup under `.odooctl/remote-backups/` so backup creation does not fail because remote upload is unavailable.

## Redaction policy

Sensitive environment variables are redacted in command output when their names contain markers like `PASSWORD`, `SECRET`, `TOKEN`, `KEY`, or `PASSWD`. Short/common values are deliberately not replaced globally because values like `odoo` make logs unreadable when over-redacted.

```yaml
redaction:
  min_secret_length: 6
  ignore_values:
    - odoo
    - admin
    - postgres
```

`odooctl doctor` warns when a referenced secret is too short or ignored by the redaction policy.

See `examples/odooctl.yml` for a complete starter configuration.
