# Disaster Recovery

odooctl provides three layers of backup/restore UX for production safety:

1. **Backup verification** — confirm a backup's integrity after creation.
2. **Restore-point browser** — list and audit all local backups with checksum integrity.
3. **DR drills** — automated drill that restores a backup into a throwaway database, healthchecks it, and cleans up.

## Backup verification

Run a backup and immediately verify its checksums:

```sh
odooctl backup production --verify
```

The `--verify` flag calls `validate_backup_dir` against the just-created backup and emits a `backup verified` operation event if checksums match. Use this as a post-backup sanity check.

You can also verify any existing backup by backup ID:

```sh
# Python API
from odooctl.services.backup import verify_backup
result = verify_backup(backups_root, "production_2026-05-31_100000")
print(result.ok, result.error)
```

## Restore-point browser

List all local restore points with integrity status:

```sh
# CLI (via the web UI or API)
GET /projects/{project}/restore-points
GET /projects/{project}/restore-points?environment=staging
```

Each restore point reports:

| Field | Description |
|-------|-------------|
| `backup_id` | Unique backup identifier |
| `environment` | Source environment |
| `timestamp` | Creation timestamp |
| `integrity` | `ok` / `failed` / `unknown` |

Integrity is verified by re-checking SHA-256 checksums against the stored manifest. A `failed` status means files are corrupt or missing.

The **Restore Points** tab in the web UI (`odooctl serve`) shows this list for each environment.

## Restore production backup to staging

Restore a production backup into staging without touching production:

```sh
odooctl restore production --to staging
odooctl restore production --to staging --backup production_2026-05-31_100000
```

Safety rules:
- The **target** environment must not be protected (production is always protected).
- The source backup is validated (checksums) but the environment mismatch check is intentionally skipped so cross-environment restores work.
- The DB dump is restored into a temporary `{target_db}{temp_db_suffix}` database first, then swapped into the target DB name before healthcheck. The target filestore is restored as part of the staging flow.
- A healthcheck is run against the target after restore.

## DR drills

A DR drill restores the latest backup into a **throwaway database**, runs a healthcheck, then drops the throwaway DB. The live database is never touched.

```sh
odooctl dr drill production
```

Steps:
1. Resolve the latest backup for the source environment.
2. Validate backup checksums.
3. Restore the DB dump into `{source_db}_dr_drill` (a throwaway DB name).
4. Run a healthcheck.
5. Drop the throwaway DB (always, even on failure).
6. Report `success` or `failed`.

Protected environments (production by default) cannot be passed as drill *targets* — the drill reads from their backups but never writes to the live DB. Since the throwaway DB is always dropped, drills are safe to run repeatedly.

### Python API (injectable fakes for testing)

```python
from odooctl.services.dr import run_dr_drill

result = run_dr_drill(
    environment="production",
    backups_root=project.backups_dir,
    db_adapter=my_db_adapter,
    fs_adapter=my_fs_adapter,
    healthcheck_fn=lambda url: True,
    is_protected_fn=config.is_protected,
)
print(result.status, result.backup_id)
```

All dependencies are injectable, making unit tests use fakes without touching real databases.

## Web UI

The **Restore Points** tab in `odooctl serve` shows restore points with integrity badges for each environment. Admin users see a **DR Drill** button that enqueues a drill operation via the API.

## Encrypted off-site backup metadata

When remote backups use S3, configure server-side encryption metadata on the remote backup block:

```yaml
backups:
  remote:
    type: s3
    bucket: demo-odoo-backups
    encryption_algorithm: aws:kms   # or AES256 for S3-managed keys
    encryption_key_env: ODOO_BACKUP_KMS_KEY_ID
```

`odooctl` records only non-secret manifest metadata:

```json
"encryption": {
  "algorithm": "aws:kms",
  "key_ref": "env:ODOO_BACKUP_KMS_KEY_ID"
}
```

For real S3 uploads, the adapter passes the matching `ServerSideEncryption` and optional `SSEKMSKeyId` `ExtraArgs` to `boto3.upload_file()`. The key ID is read from the named environment variable and is not written to the manifest or logs. If boto3 is unavailable and the adapter falls back to the local mirror used by tests/offline runs, the mirror is a local copy and should not be treated as an encrypted off-site destination.

## Safety invariants

- Production is never used as a restore *target* (enforced in `restore_to_env`).
- Restore-to-staging restores the DB into a temporary incoming DB and swaps before target healthcheck.
- DR drill throwaway DB is always dropped in a `finally` block.
- Backup checksums are verified before any restore or drill.
- Remote S3 encryption metadata is recorded in the backup manifest and real boto3 uploads request S3 server-side encryption; no key material is stored.
