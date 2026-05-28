# Multi-database local Odoo example

This example shows a local/staging shape where one Docker Compose Odoo service serves multiple databases on the same host and port.

Use this mode for local experiments, QA sandboxes, or single-box staging rehearsals. For real public production/staging deployments, prefer distinct domains or routes unless you intentionally operate Odoo's database selector.

## Key settings

- `runtime.execution_mode: docker` — backup/restore/clone use PostgreSQL tools inside the DB service.
- Same `stack`, `domain`, and `port` for production and staging.
- Distinct `db_name` and `filestore_path` for each environment.
- `db_selector: true` — health checks append `?db=<db_name>`.
- Shared `filestore_volume` — the Odoo named volume contains per-database filestore directories.

## Example flow

```bash
export ODOO_DB_PASSWORD=odoo
odooctl validate --config examples/multidb/odooctl.yml
odooctl doctor --config examples/multidb/odooctl.yml
odooctl backup production --config examples/multidb/odooctl.yml
odooctl clone production staging --sanitize --config examples/multidb/odooctl.yml
odooctl update-modules staging --modules base --config examples/multidb/odooctl.yml
```

A healthy local login route may return HTTP `302 FOUND`; Odoo redirects on `/web/login` and that is acceptable.

## Reference fixture

For a real runnable Odoo 19 Community fixture, see `experiments/odoo19-community-staging/`.
