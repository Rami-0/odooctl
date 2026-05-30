# odooctl Catalog

The catalog is odooctl's registry of declarative manifests for stack templates, addon sources, addon packs, and companion services. It is a declarative reference for setting up new projects — not a package manager. The catalog does not install, clone, or deploy anything on its own.

## Catalog commands

```
odooctl catalog list              # Table of all bundled catalog entries
odooctl catalog show <id>         # Full YAML dump of a catalog entry
odooctl catalog add <manifest>    # Validate a user manifest and list the IDs it defines
```

`catalog add` validates the manifest schema and reports entry IDs. It does not persist state. To use custom entries in a command, pass the manifest via `--catalog PATH` on the command that supports it (currently `setup`).

## Bundled stack templates

Stack templates declare a complete Odoo + PostgreSQL image pair and default compose configuration. The bundled templates cover the two current LTS-adjacent community releases:

| ID | Odoo version | Odoo image | PostgreSQL image |
|----|-------------|-----------|-----------------|
| `odoo-18-community` | 18.0 | `odoo:18.0` | `postgres:15-alpine` |
| `odoo-19-community` | 19.0 | `odoo:19.0` | `postgres:16-alpine` |

Both templates set `http_port: 8069` and declare named Docker volumes for Odoo data and the PostgreSQL data directory.

## Bundled addon sources and packs

Addon sources identify a Git repository that contains Odoo addons:

| ID | Description | Repository |
|----|-------------|-----------|
| `oca-web` | OCA web addons (web_responsive, web_dialog_size, …) | `https://github.com/OCA/web` ref `18.0` |
| `oca-server-tools` | OCA server-tools (base_setup_partner, …) | `https://github.com/OCA/server-tools` ref `18.0` |

Addon packs group one or more sources under a single ID:

| ID | Included sources |
|----|-----------------|
| `oca-web-essentials` | `oca-web`, `oca-server-tools` |

## Bundled companion services

Companion services are optional Docker Compose service definitions that can be added alongside an Odoo deployment:

| ID | Image | Purpose |
|----|-------|---------|
| `pgadmin` | `dpage/pgadmin4:8.6` | Web-based PostgreSQL admin UI (port 5050) |
| `mailhog` | `mailhog/mailhog:v1.0.1` | SMTP mail catcher for development and staging |
| `minio` | `minio/minio:RELEASE.2024-05-01T01-11-10Z` | S3-compatible object storage for filestore offload and backup targets |
| `n8n` | `n8nio/n8n:1.40.0` | Workflow automation and Odoo webhook integrations |

Inspect a companion service entry with `odooctl catalog show <id>` to see its ports, volumes, and required environment variables before adding it to a compose file.

## Setup integration

`odooctl setup` uses the catalog to scaffold a new `odooctl.yml`:

```bash
# Interactive wizard using the bundled catalog
odooctl setup

# Non-interactive with a bundled stack
odooctl setup --yes --stack odoo-19-community --name myproject

# Load a user manifest for this invocation, then use a custom stack from it
odooctl setup --catalog my-catalog.yaml --stack acme-odoo-19 --yes --name myproject

# Legacy stacks (odoo-17-community, odoo-16-community) are also accepted
# for backward compatibility with existing configs.
odooctl setup --stack odoo-17-community --yes --name legacy-project
```

The `--catalog PATH` option loads the given manifest and merges its entries with the bundled catalog for that single invocation. The bundled catalog is unchanged; the user manifest entries are not persisted.

## User manifest extension

Create a YAML file with one or more catalog entries and pass it via `--catalog PATH`. The file may contain a single entry or a list of entries:

```yaml
# my-catalog.yaml
- kind: StackTemplate
  id: acme-odoo-19
  description: "ACME internal Odoo 19 stack with private registry"
  odoo_version: "19.0"
  odoo_image: "registry.acme.com/odoo:19.0-2024q4"
  postgres_image: "postgres:16-alpine"
  http_port: 8069

- kind: AddonSource
  id: acme-internal-addons
  description: "ACME private addon monorepo"
  repo_url: "https://github.com/acme/odoo-addons"
  ref: "19.0"
  subpath: "addons"
  auth_env: "ACME_GITHUB_TOKEN"

- kind: CompanionService
  id: acme-redis
  description: "Redis for Odoo session cache"
  service_name: redis
  image: "redis:7.2-alpine"
  ports:
    - "6379:6379"
  environment: {}
  volumes:
    - redis-data:/data
```

Use `odooctl catalog add my-catalog.yaml` to validate the manifest before using it in setup.

## Safety rules

### 1 — No floating `:latest` in production-grade templates

The catalog schema rejects image references ending in `:latest` for `StackTemplate` (both `odoo_image` and `postgres_image`) and `CompanionService.image`. Pin every image to a specific version tag so deployments are reproducible and upgrades are deliberate.

```yaml
# BAD — rejected by the schema
odoo_image: "odoo:latest"

# GOOD
odoo_image: "odoo:19.0"
```

### 2 — Private credentials via environment variable references only

`AddonSource.auth_env` stores the *name* of an environment variable that holds the repository authentication token — never a literal credential value. The value is resolved at runtime from the operator's environment.

```yaml
# BAD — literal token
auth_env: "ghp_XXXXXXXXXXXX"

# GOOD — env-var name that odooctl passes to git at clone time
auth_env: "GITHUB_TOKEN"
```

`CompanionService.environment` values must reference environment variables using Docker Compose `${VAR}` or `${VAR:-default}` syntax, not inline credentials:

```yaml
environment:
  # BAD — literal secret inline
  PGADMIN_DEFAULT_PASSWORD: "supersecret"

  # GOOD — resolved from the operator's environment at compose-up time
  PGADMIN_DEFAULT_PASSWORD: "${PGADMIN_PASSWORD}"
```

### 3 — The catalog is declarative, not a package manager

The catalog describes *what* a stack or service looks like; it does not pull images, clone repositories, or modify your Docker Compose files automatically. Every catalog-driven action is an explicit operator command (`setup`, `catalog add`). The catalog has no install, remove, or upgrade lifecycle of its own.

## Manifest schema reference

All catalog entries share a `kind` discriminator field. Required and optional fields by kind:

### StackTemplate

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `kind` | `"StackTemplate"` | yes | discriminator |
| `id` | string | yes | unique identifier |
| `description` | string | no | human-readable summary |
| `odoo_version` | string | yes | e.g. `"19.0"` |
| `odoo_image` | string | yes | no `:latest` |
| `postgres_image` | string | yes | no `:latest` |
| `http_port` | int | no | default `8069` |
| `volumes` | list[string] | no | named Docker volumes |
| `compose_defaults` | dict | no | extra compose keys merged at render time |

### AddonSource

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `kind` | `"AddonSource"` | yes | discriminator |
| `id` | string | yes | unique identifier |
| `description` | string | no | |
| `repo_url` | string | yes | HTTPS or SSH git remote |
| `ref` | string | yes | branch, tag, or SHA |
| `subpath` | string | no | subdirectory within the repo |
| `auth_env` | string | no | env-var *name* for token auth; no literals |

### AddonPack

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `kind` | `"AddonPack"` | yes | discriminator |
| `id` | string | yes | unique identifier |
| `description` | string | no | |
| `sources` | list[string] | no | list of `AddonSource` IDs |

### CompanionService

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `kind` | `"CompanionService"` | yes | discriminator |
| `id` | string | yes | unique identifier |
| `description` | string | no | |
| `service_name` | string | yes | Docker Compose service name |
| `image` | string | yes | no `:latest` |
| `ports` | list[string] | no | host:container port mappings |
| `environment` | dict[str, str] | no | use `${VAR}` references only |
| `volumes` | list[string] | no | named Docker volumes |
