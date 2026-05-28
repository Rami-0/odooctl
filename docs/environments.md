# Environments

`odooctl` treats each named environment as an operational target: branch, URL, database, filestore, clone policy, sanitization, and module update list.

Common commands:

```bash
odooctl env list
odooctl env show production
odooctl env create staging --clone-from production --sanitize
odooctl env destroy staging --yes
odooctl env destroy qa --purge --yes
```

Safety rules:

- `production` cannot be a clone target.
- `env destroy` refuses `production`.
- `env destroy --purge` removes the non-production database and filestore only after the production guard passes.
- `clone production staging --sanitize` restores into a temporary DB, sanitizes it, then swaps it into place.

## Separate stack vs multi-db

For real production/staging deployments, prefer separate domains or stacks.

For local one-box experiments, set both environments to the same `stack`, same `domain`, and `db_selector: true`. Health checks append `?db=<db_name>` so the shared Odoo service selects the correct database.
