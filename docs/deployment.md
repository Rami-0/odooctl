# Deployment

`odooctl deploy production --branch main` performs a pre-deploy backup, checks out/pulls the branch, pulls and starts Docker Compose services, runs module updates, performs health checks, and stores deployment metadata.

`odooctl deploy staging --branch staging` follows the same flow without mandatory production backup.
