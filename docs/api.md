# odooctl Local API

The optional local API exposes project and operation management over HTTP. It is
intentionally unprivileged: it reads state, enqueues operations, and streams
events — but never touches Docker, Postgres, or the filestore directly. Mutating
work is delegated to the privileged runner via the durable queue.

## Installation

FastAPI and uvicorn are optional extras:

```bash
pip install odooctl[api]
```

## Starting the server

```bash
# Localhost-only (default) on port 8787
export ODOOCTL_API_KEY="your-hmac-key"
odooctl serve

# Custom host/port with a pre-built SPA
odooctl serve --host 0.0.0.0 --port 8080 --static-dir ./spa/dist
```

The server binds to `127.0.0.1` by default (`TrustedHostMiddleware`). Passing
`--host 0.0.0.0` in a production setup requires additional network controls.

## Starting the runner

The privileged runner must run as a user with Docker socket and filestore access:

```bash
export ODOOCTL_API_KEY="your-hmac-key"   # same key as the API server
odooctl runner              # loop forever
odooctl runner --once       # process one operation and exit
```

## Authentication

All requests require a bearer token:

```
Authorization: Bearer <token>
```

Tokens are minted with `odooctl security token mint` (see `docs/rbac.md`):

```bash
# Operator token valid for 8 hours
odooctl security token mint \
  --action api --environment "*" --project "*" \
  --key-env ODOOCTL_API_KEY \
  --ttl 28800 \
  --role operator
```

Token payload fields:

| Field    | Description                                              |
|----------|----------------------------------------------------------|
| `act`    | Token action scope (`"api"` for session tokens)          |
| `env`    | Environment scope (`"*"` for session tokens)             |
| `proj`   | Project scope (`"*"` for session tokens)                 |
| `roles`  | List of roles: `["viewer"]` or `["operator"]`, etc.      |
| `iat`    | Issued-at Unix timestamp                                 |
| `exp`    | Expiry Unix timestamp                                    |
| `nonce`  | Random per-token nonce (enables future single-use checks)|

## RBAC roles

| Role       | Allowed operations                                          |
|------------|-------------------------------------------------------------|
| `viewer`   | Read-only: projects, environments, status, backups, audit   |
| `operator` | Viewer + backup, deploy, clone, restore                     |
| `admin`    | Operator + promote, env management, secrets                 |
| `owner`    | All actions including protected-environment destructive ops |

## Routes

### Projects

| Method | Path                                    | Required role | Description                        |
|--------|-----------------------------------------|---------------|------------------------------------|
| GET    | `/projects`                             | viewer        | List all registered projects       |
| GET    | `/projects/{project}`                   | viewer        | Get project info                   |
| GET    | `/projects/{project}/environments`      | viewer        | List environments from config      |
| GET    | `/projects/{project}/status`            | viewer        | Metadata-derived status            |
| GET    | `/projects/{project}/backups`           | viewer        | List backup manifests              |
| GET    | `/projects/{project}/audit`             | viewer        | Read audit trail entries           |

**Status note**: `GET /projects/{project}/status` returns metadata-store-derived
state (last deployment commit, last backup timestamp). It does NOT run
`docker compose ps`; live container status requires a queued operation via the
runner.

### Operations

| Method | Path                                   | Required role | Description                         |
|--------|----------------------------------------|---------------|-------------------------------------|
| POST   | `/projects/{project}/operations`       | operator+     | Enqueue a mutating operation        |
| GET    | `/operations/{id}`                     | viewer        | Fetch operation record              |
| GET    | `/operations/{id}/events`              | viewer        | Stream operation events (SSE)       |
| POST   | `/operations/{id}/cancel`              | viewer        | Cancel a queued operation           |

#### POST /projects/{project}/operations

Request body:

```json
{
  "kind": "backup",
  "environment": "production",
  "params": {}
}
```

Runner-supported `kind` values: `backup`, `clone`.

Other kinds (`restore`, `deploy`, `promote`, `env_create`, `env_destroy`,
`update_modules`, `rollback`) are accepted by the API and recorded in the
operation store, but the runner does not yet implement their dispatch and will
mark them as `failed`.

User-supplied `params` are redacted (via `odooctl.security.redaction.redact`)
before being recorded in the operation store and queue entry.

Response (202 Accepted):

```json
{
  "op_id": "abc123def456",
  "kind": "backup",
  "project": "my-project",
  "environment": "production",
  "status": "queued",
  "created_at": "2026-05-30T12:00:00+00:00"
}
```

#### GET /operations/{id}/events

Returns a `text/event-stream` (SSE) response. Each event is a JSON-encoded
operation event:

```
data: {"op_id":"abc123","seq":0,"timestamp":"...","level":"info","phase":"start","message":"operation started: backup on production","data":{}}

data: {"op_id":"abc123","seq":1,"timestamp":"...","level":"info","phase":"backup","message":"backup complete: bk-20260530-120001","data":{}}
```

The stream terminates when the operation reaches `succeeded`, `failed`, or
`cancelled`. Pass `?max_polls=N` to limit poll iterations (useful in tests or
short-lived clients).

## Security model

- **API / runner split**: the API never imports `odooctl.adapters` or
  `odooctl.odoo`. All privileged work runs in the separate runner process. This
  is enforced structurally by `odooctl security runner-check`.
- **Capability tokens**: when the API enqueues an operation, it mints a
  short-lived HMAC-signed capability token scoped to the exact
  action/environment/project. The runner verifies this token before executing,
  preventing forged queue entries even if the queue directory is writable.
- **Nonce tracking**: the runner records consumed token nonces in
  `{state_dir}/consumed_nonces.json` (e.g. `.odooctl/consumed_nonces.json`)
  to prevent token replay within the TTL.
- **Param redaction**: user-supplied operation params are passed through
  `odooctl.security.redaction.redact` before being stored or logged.
- **Localhost-only default**: `TrustedHostMiddleware` restricts the API to
  `127.0.0.1` / `localhost` by default.

## Queue format

The durable queue lives at `{project_root}/.odooctl/queue/`. Each entry is a
JSON file named `{op_id}.json`:

```json
{
  "op_id": "abc123def456",
  "kind": "backup",
  "project": "my-project",
  "environment": "production",
  "actor": "api-client",
  "params_redacted": {},
  "token": "<capability-token>",
  "created_at": "2026-05-30T12:00:00+00:00"
}
```

The runner claims an entry by atomically renaming `{op_id}.json` →
`{op_id}.running`. On success it removes the file; on failure it renames it to
`{op_id}.failed`.
