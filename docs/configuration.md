# Configuration

Run `odooctl init` to create `odooctl.yml`.

Guidelines:

- Keep secrets out of YAML.
- Use `password_env` and provider-specific environment variable references.
- Define both `production` and `staging` environments so clone/deploy flows can stay explicit.
- Point `staging.clone_from` at the source environment you want to clone.

Key sections:

- `project`: project name and Odoo version.
- `runtime`: Docker Compose file and reverse-proxy mode.
- `environments`: per-environment branch, domain, database, filestore, clone source, sanitization flag, and module update list.
- `postgres`: connection settings plus the environment variable that holds the password.
- `odoo`: image, config path, addons paths, and service name.
- `backups`: local backup path, optional remote storage, and retention policy.
- `sanitization`: SQL files and built-in staging safety toggles.
- `healthcheck`: path and retry timing used after clone/deploy/restore operations.

See `examples/odooctl.yml` for a complete starter configuration.
