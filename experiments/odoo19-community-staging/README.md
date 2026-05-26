# Odoo 19 Community staging experiment

Date: 2026-05-26
Agent/model: default Hermes model, OpenAI Codex GPT-5.5
Repo: `/home/dev/odooctl`

## Purpose

Deploy a real local Odoo 19 Community Edition stack, exercise `odooctl` against it, create a production/staging shape, and record what works, what breaks, and what `odooctl` still needs before it can operate comfortably on real Odoo projects.

## Current experiment artifacts

- `docker-compose.yml` — local Odoo 19.0 + PostgreSQL 17 stack.
- `odooctl.yml` — experiment config targeting `production` and `staging` environments.
- `.sanitize/staging.sql` — harmless placeholder sanitization SQL hook.
- `README.md` — this report.

## Environment verified

- Docker: `Docker version 29.4.2`
- Docker Compose: `v5.1.3`
- Python: `3.11.15`
- Odoo image tags: both `odoo:19` and `odoo:19.0` exist on Docker Hub.
- Running Odoo image reports: `Odoo version 19.0-20260513`.

## What was deployed

Started this stack:

```bash
cd /home/dev/odooctl
export ODOO_DB_PASSWORD=odoo
python -m odooctl validate --config experiments/odoo19-community-staging/odooctl.yml
docker compose -f experiments/odoo19-community-staging/docker-compose.yml up -d
```

Result:

- PostgreSQL container became healthy.
- Odoo container started.
- `http://localhost:18069/web/login` responded with HTTP redirect to the database selector before DB initialization.

## Database initialization

Created an Odoo production database manually inside the Odoo container:

```bash
docker compose -f docker-compose.yml exec -T odoo \
  odoo -d odoo_prod -i base --without-demo=all --stop-after-init \
  --db_host=db --db_user=odoo --db_password=odoo
```

Notes:

- Odoo 19 logs a warning: `option --without-demo: since 19.0, invalid boolean value: 'all', assume True`.
- This means `--without-demo=all` still works but is no longer the clean Odoo 19 syntax. Prefer `--without-demo=True` or equivalent if supported by the target version.

## Staging clone attempt

`odooctl clone --preview` works:

```bash
python -m odooctl clone production staging --sanitize --config odooctl.yml --preview
```

Observed output correctly summarized:

- source: production
- target: staging
- source branch: main
- target branch: staging
- production source: yes
- staging URL: `https://localhost:18070`

A manual database-level staging clone was then attempted through the PostgreSQL container:

```bash
docker compose -f docker-compose.yml exec -T db sh -lc '
  dropdb -U odoo --if-exists odoo_staging &&
  createdb -U odoo odoo_staging &&
  pg_dump -U odoo -Fc odoo_prod | pg_restore -U odoo -d odoo_staging --clean --if-exists
'
```

Result:

- `odoo_staging` exists.
- Query verification succeeded:

```sql
SELECT current_database(), count(*) FROM ir_module_module;
```

returned `odoo_staging` and `695` modules.

After restarting Odoo, both database-specific login URLs responded:

```bash
curl -I 'http://localhost:18069/web/login?db=odoo_prod'
curl -I 'http://localhost:18069/web/login?db=odoo_staging'
```

Both returned HTTP `302 FOUND`.

## What works

1. `odooctl validate`
   - Correctly validates the experiment config.
   - Correctly requires unique environment domains.
   - Correctly verifies referenced environment variables when `ODOO_DB_PASSWORD` is set.

2. Docker-based Odoo 19 Community startup
   - Official `odoo:19.0` image starts cleanly with PostgreSQL 17.
   - `/web/login` is reachable on the mapped host port.

3. Odoo 19 database creation
   - Manual `odoo -d odoo_prod -i base --stop-after-init --db_host=db --db_user=odoo --db_password=odoo` succeeds.

4. `odooctl status`
   - Produces structured JSON.
   - Shows current git commit and configured environment metadata.

5. `odooctl clone --preview`
   - Useful and side-effect-free.
   - Summarizes source/target, sanitization, branches, and staging URL clearly.

6. `odooctl logs`
   - Successfully tails Docker Compose service logs.
   - Secret redaction is active; logs redact occurrences of sensitive terms like `odoo` because the password was `odoo`.

7. Manual staging clone viability
   - A production DB can be cloned to a staging DB inside the Docker network using `pg_dump | pg_restore`.
   - Odoo can serve both databases from one running service when selected by `?db=`.

## What did not work / gaps found

### 1. Host PostgreSQL client tools are required but not preflighted

`odooctl backup production` failed because the host does not have `pg_dump` installed:

```text
FileNotFoundError: [Errno 2] No such file or directory: 'pg_dump'
```

The PostgreSQL container does have `pg_dump`, but `odooctl` currently assumes local host binaries.

Need:

- Add preflight checks for `pg_dump`, `pg_restore`, `psql`, and probably `createdb/dropdb` before backup/restore/clone.
- Or add a Docker Compose execution mode that uses the database container's PostgreSQL client tools.
- Error message should say exactly which binary is missing and how to fix it.

### 2. `update-modules` fails with official Odoo Docker image unless DB flags are passed

`odooctl update-modules production --modules base` failed because it runs:

```bash
docker compose -f docker-compose.yml exec -T odoo odoo -d odoo_prod -u base --stop-after-init
```

Inside the official Odoo image, direct `odoo` invocation did not pick up the container's `HOST`, `USER`, and `PASSWORD` environment variables the same way the image entrypoint does. Odoo tried the local socket/default connection:

```text
database: default@default:default
connection to server on socket "/var/run/postgresql/.s.PGSQL.5432" failed
```

Manual command succeeds when DB flags are passed:

```bash
docker compose -f docker-compose.yml exec -T odoo \
  odoo -d odoo_prod -u base --stop-after-init \
  --db_host=db --db_user=odoo --db_password=odoo
```

Need:

- `odooctl` should pass DB connection flags when invoking `odoo` inside the service.
- Config likely needs explicit Docker-internal DB host/user/password mapping separate from host-side PostgreSQL access.
- Alternatively require `odoo.conf` to exist and pass `-c /etc/odoo/odoo.conf` or a mounted config path.

### 3. HTTPS is assumed for localhost domains

`odooctl status` reported health URLs like:

```text
https://localhost:18069/web/login
```

The local Odoo container is plain HTTP.

Need:

- Add `scheme: http|https` per environment, or allow domains to include scheme.
- Avoid hardcoding HTTPS for local/dev Docker experiments.

### 4. Config expects unique domains but single-service local staging uses DB names

The validator rejected production and staging sharing `localhost:18069`:

```text
Environments 'production' and 'staging' cannot share domain 'localhost:18069'
```

That safety rule is correct for real deployments, but local Odoo often serves multiple databases behind one HTTP service and selects DB by query/session/dbfilter.

Need:

- Keep current production safety rule.
- Add an explicit local/multidb mode for experiments where environments differ by DB name, not host/domain.
- Healthcheck URL should support `?db=<db_name>` in that mode.

### 5. Real clone/sanitization cannot yet be judged end-to-end through `odooctl`

Because host `pg_dump` is missing and because Docker-internal DB execution is not implemented, real `odooctl clone production staging --sanitize` is expected to fail in this environment before reaching the meaningful Odoo sanitization checks.

Need:

- Docker-native clone path.
- Better preflight report showing all required host/container dependencies before starting.
- A safe local fixture that creates prod DB, inserts representative outbound integrations, clones to staging, sanitizes, and verifies sanitized state.

### 6. Filestore paths are not solved for Docker volumes

The Odoo service stores filestore data under a Docker volume at `/var/lib/odoo`, but the experiment config uses local paths like `./filestore/odoo_prod`.

Need:

- Docker volume-aware filestore backup/restore support.
- Or documented required bind mount layout for `odooctl` compatibility.
- Preflight should verify that configured `filestore_path` exists and is readable before backup/clone.

### 7. Live DB clone can disturb running Odoo cron workers

During manual staging clone, Odoo logs showed cron warnings and a real-time limit reload around `odoo_staging`. This is likely because Odoo saw/used the staging DB while it was still being restored.

Need:

- Clone flow should restore into an isolated temp DB name, sanitize there, then atomically rename/swap to staging if possible.
- Or stop Odoo/disable db listing/disable cron during clone.
- Sanitization should disable crons before the staging DB becomes visible to a running Odoo service.

### 8. Secret redaction is too broad when the password is a common token

Because `ODOO_DB_PASSWORD=odoo`, log output redacted every occurrence of `odoo`, making logs harder to read.

Need:

- Keep redaction, but avoid redacting very short/common values or known product names.
- At minimum, warn users not to use common words as secrets in test environments if they want readable logs.

### 9. Test suite is sensitive to exported real environment variables

Running the test suite with `ODOO_DB_PASSWORD=odoo` exported caused one test to fail because the deploy preflight moved past the missing-env check and then failed on missing `psql`:

```text
1 failed, 96 passed
RuntimeError: Postgres connectivity check failed ... No such file or directory: 'psql'
```

Running with that variable unset succeeds:

```bash
env -u ODOO_DB_PASSWORD pytest -q
# 97 passed
```

Need:

- Tests should isolate environment variables with `monkeypatch.delenv(...)` where behavior depends on missing env vars.
- Integration tests should be separated from unit tests and explicitly opt into real environment/dependency checks.

## Immediate product needs for `odooctl`

1. Dependency preflight command

```bash
odooctl doctor --config odooctl.yml
```

Should check:

- Docker/Compose availability.
- Compose file exists and services exist.
- DB connectivity from host or selected execution mode.
- Required binaries: `pg_dump`, `pg_restore`, `psql` if host mode.
- Required env vars.
- Filestore path access.
- Healthcheck URL scheme and reachability.

2. Separate host DB access from container DB access

Current config has one PostgreSQL block. Real Docker deployments need two contexts:

- host/backup context: how `odooctl` reaches PostgreSQL from the operator machine.
- container/Odoo context: how `odoo` reaches PostgreSQL inside Compose.

3. Docker-native backup/restore/clone execution mode

For self-hosted Docker Compose, it is common that PostgreSQL is not exposed on the host. `odooctl` should support running `pg_dump`, `pg_restore`, and `psql` inside the DB service.

4. Odoo command invocation should include DB flags/config

`update-modules`, deploy module updates, and similar commands should not assume direct `odoo` invocation inside the container knows how to reach Postgres.

5. HTTP/HTTPS environment config

Add scheme support and support local HTTP cleanly.

6. Local multi-db experiment mode

Useful for staging experiments where production/staging are two DBs served by one local Odoo process.

7. Safer staging clone choreography

Restore to temp DB, sanitize, then expose as staging. Avoid live partially-restored DB visibility.

## Next actions proposed

1. Implement `odooctl doctor` first. It will make real deployment failures understandable.
2. Add Docker-native Postgres adapter mode: run DB tools through `docker compose exec -T db ...`.
3. Add DB connection flags/config to Odoo module update execution.
4. Add `scheme` and `healthcheck.query_params` or environment DB selector support.
5. Add an integration test fixture based on this experiment folder.

## Current running URLs

- Odoo service: `http://localhost:18069`
- Production DB login: `http://localhost:18069/web/login?db=odoo_prod`
- Staging DB login: `http://localhost:18069/web/login?db=odoo_staging`

## Cleanup

To stop the experiment:

```bash
cd /home/dev/odooctl/experiments/odoo19-community-staging
docker compose down
```

To remove volumes too:

```bash
docker compose down -v
```
