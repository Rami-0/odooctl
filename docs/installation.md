# Installation

```bash
uv venv
uv pip install -e .
odooctl --help
```

Runtime prerequisites on the deployment host: Docker Compose, PostgreSQL client tools (`pg_dump`, `pg_restore`, `psql`, `createdb`, `dropdb`), `tar` with zstd support, and access to the Odoo filestore path.
