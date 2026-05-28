# Installation

`odooctl` is packaged as a normal Python CLI. The recommended operator install is an
isolated tool environment, not a checkout-specific virtualenv.

## Recommended: pipx

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install odooctl
odooctl --help
```

Upgrade later with:

```bash
pipx upgrade odooctl
```

## Alternative: uv tool

```bash
uv tool install odooctl
odooctl --help
```

Upgrade later with:

```bash
uv tool upgrade odooctl
```

## Development install from a checkout

```bash
uv venv
uv pip install -e '.[dev]'
pytest -q
```

## Optional S3 dependencies

The core package intentionally avoids cloud SDK dependencies. Install the optional
S3 extra only on hosts that use a future real S3 remote adapter:

```bash
pipx inject odooctl 'odooctl[s3]'
# or for uv tool installs:
uv tool install 'odooctl[s3]'
```

## Runtime prerequisites

A Python package manager only installs the `odooctl` CLI. The deployment host still
needs the platform tools used to operate Odoo.

Required for Docker Compose projects:

- Docker Engine with the Compose plugin (`docker compose version`).
- Access to the project repo that contains `odooctl.yml` and `docker-compose.yml`.
- `tar` for plain `filestore.tar` filestore archives.

Database tooling depends on `runtime.execution_mode`:

- `execution_mode: docker` (recommended default for Docker Compose stacks): PostgreSQL
  tools run inside the configured database service, so the host does not need
  `pg_dump`, `pg_restore`, `psql`, `createdb`, or `dropdb`.
- `execution_mode: host`: install host PostgreSQL client tools (`pg_dump`,
  `pg_restore`, `psql`, `createdb`, `dropdb`) and ensure the configured database is
  reachable from the operator host.

After installation, register or select a project and run doctor:

```bash
odooctl project add acme --path /srv/odoo/acme
odooctl -p acme doctor
```

For an unregistered checkout:

```bash
odooctl -C /srv/odoo/acme doctor
```
