# Rollback

Code rollback and full rollback are intentionally separate.

- `odooctl rollback production --mode code`: check out the last successfully deployed commit recorded in `.odooctl/deployments/` before the current deployment for the environment, then redeploy the Odoo service. This does not restore database or filestore state.
- `odooctl rollback production --mode full --backup <id>`: restore database and filestore from a backup, then deploy. This can discard new production data after the backup.

Code rollback refuses to run when no successful deployment commit is recorded. In that case, use a full rollback with an explicit backup or perform a manual git recovery after human review.

Both rollback modes restart the configured Odoo service and then verify the environment healthcheck URL (`https://<domain><healthcheck.path>`). If the healthcheck fails after the service is brought up, `odooctl rollback` exits with that failure instead of reporting a successful rollback.
