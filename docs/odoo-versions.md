# Odoo version notes

`odooctl` is version-aware where Odoo CLI behavior or Docker images differ, but it intentionally keeps configuration explicit instead of guessing too much from an image tag.

## Supported baseline

The current production-readiness validation used:

- Odoo image: `odoo:19.0`
- Odoo runtime version: `19.0-20260513`
- PostgreSQL image: `postgres:17`
- Docker Compose stack with services named `odoo` and `db`

The same Docker-native execution model is intended for recent official Odoo images, provided your compose service has PostgreSQL client tools available in the DB container and the Odoo service can run the `odoo` CLI.

## Config fields to review per version

### `odoo.image`

Set the image tag you actually deploy:

```yaml
odoo:
  image: odoo:19.0
```

Verify tag availability before using a new major version in production.

### `odoo.without_demo`

Odoo 19 warns when older examples use `--without-demo=all` and treats it as true. Prefer:

```yaml
odoo:
  without_demo: "True"
```

Older Odoo deployments that still require `all` can override this value explicitly.

### Module updates

Docker module updates are invoked with explicit DB connection flags:

```text
odoo -d <db> -u <modules> --stop-after-init --db_host=<host> --db_user=<user> --db_password=<password>
```

This avoids relying on official-image entrypoint environment handling, which is not always applied to direct `docker compose exec odoo odoo ...` calls.

### Health checks

Odoo login endpoints commonly return HTTP `302` redirects. `odooctl` treats 2xx and 3xx responses as healthy.

For local or shared-stack multi-database setups, use:

```yaml
environments:
  staging:
    db_selector: true
```

This makes health checks include `?db=<db_name>`.

## Upgrade checklist

When moving a project to a new Odoo major version:

1. Pull and start the target image in a staging stack.
2. Run `odooctl doctor` with the new config.
3. Run `odooctl backup production` in the old known-good stack.
4. Restore or clone into a staging database on the new image.
5. Run `odooctl update-modules staging --modules <your modules>`.
6. Confirm `/web/health` and any custom health route return HTTP 200 (redirects count as unhealthy).
7. Review Odoo logs for deprecated CLI flags or addon migration warnings.

## Integration coverage

The checked-in experiment under `experiments/odoo19-community-staging/` is the reference fixture for Odoo 19 Community Docker behavior. Use it as the model for service names, Docker-native DB access, filestore named volumes, and local multi-DB `db_selector` health checks.
