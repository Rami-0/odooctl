# Backup and Restore

`odooctl backup production` creates a backup directory with:

- `db.dump`
- `filestore.tar`
- redacted `odoo.conf.redacted` when an Odoo config file exists
- `git_commit.txt`
- `docker_image.txt`
- `manifest.json` with checksums

`odooctl restore staging --backup latest` recreates the target database, restores the dump, restores the filestore, applies target-safe config through the Odoo project config, and runs health checks.

## Execution modes

For Docker Compose stacks, prefer:

```yaml
runtime:
  execution_mode: docker
postgres:
  service: db
  internal_host: db
```

In Docker mode, `odooctl` runs PostgreSQL dump/restore through `docker compose exec -T <db-service>` and keeps custom-format dumps binary-safe. This works when PostgreSQL is not exposed on the host.

Host mode runs `pg_dump`, `pg_restore`, and `psql` on the operator host and requires host PostgreSQL client tools plus network access to the DB.

## Remote S3 copies

Add the optional dependency and configure `backups.remote` for real S3 upload:

```bash
pipx install 'odooctl[s3]'
```

```yaml
backups:
  remote:
    type: s3
    bucket: acme-odoo-backups
    prefix: acme/production
    region: eu-central-1
```

Credentials use normal AWS resolution, or explicit env references:

```yaml
    access_key_env: ODOO_S3_ACCESS_KEY
    secret_key_env: ODOO_S3_SECRET_KEY
    endpoint_env: ODOO_S3_ENDPOINT
```

If `boto3` or remote credentials are unavailable, backup creation continues and a warning explains that the remote copy was mirrored locally under `.odooctl/remote-backups/`.
