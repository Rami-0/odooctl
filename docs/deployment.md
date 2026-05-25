# Deployment

`odooctl deploy production --branch main` performs a pre-deploy backup, checks out/pulls the branch, pulls and starts Docker Compose services, runs module updates, performs health checks, and stores deployment metadata.

`odooctl deploy staging --branch staging` follows the same flow without mandatory production backup.

`odooctl restore staging --backup latest` restores the selected backup, verifies checksums, runs the health check, and prints the restored backup id.

For CI/CD, `odooctl github-actions` generates a starter GitHub Actions workflow that exposes staging/production deploys as a manual dispatch job.

See `docs/operations/deploy-staging-production.md` for the operator workflow and branch/environment rules.
