# Backup and Restore

`odooctl backup production` creates a backup directory with `db.dump`, `filestore.tar.zst`, redacted config snapshot when present, git/image references, and `manifest.json`.

`odooctl restore staging --backup latest` recreates the target database, restores the dump, restores the filestore, applies target-safe config through the Odoo project config, and runs health checks.
