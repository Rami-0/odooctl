# Rollback

Code rollback and full rollback are intentionally separate.

- `odooctl rollback production --mode code`: redeploy previous code/image only.
- `odooctl rollback production --mode full --backup <id>`: restore database and filestore from a backup, then deploy. This can discard new production data after the backup.
