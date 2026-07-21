# Deployment

`odooctl deploy production --branch main` performs a pre-deploy backup, checks out/pulls the branch, pulls and starts Docker Compose services, runs module updates, performs health checks, and stores deployment metadata.

Deploy refuses to run when the git worktree has uncommitted changes. Commit or stash local edits before deploying so the recorded metadata and checkout/pull steps describe an intentional, reproducible code state.

If a production deploy fails, `odooctl deploy` may restart the service as a recovery attempt, but it does not automatically roll back code or data; use `odooctl rollback production --mode code` or `odooctl rollback production --mode full` for an explicit rollback.

`odooctl deploy staging --branch staging` follows the same flow without mandatory production backup.

`odooctl restore staging --backup latest` restores the selected backup, verifies checksums, runs the health check, and prints the restored backup id.

For CI/CD, the primary model is pull-based: `odooctl sync <env>` on a systemd timer deploys automatically when the environment's branch has new commits and `auto_deploy: true` — see [Git sync (CI/CD)](git-sync.md). As a secondary, push-based option, `odooctl github-actions` generates a starter GitHub Actions workflow that exposes staging/production deploys as a manual dispatch job (requires a self-hosted runner).

See `docs/operations/deploy-staging-production.md` for the operator workflow and branch/environment rules.
