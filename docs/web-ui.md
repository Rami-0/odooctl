# odooctl Web UI

Vanilla JS single-page application served by `odooctl serve`.

## Architecture

The SPA is a single `dist/` directory of hand-authored HTML, CSS, and plain
JavaScript — no build tooling, no bundler, no Node.js required.

**How it is served:**
`odooctl/api/app.py` registers a catch-all FastAPI route
(`GET /{full_path:path}`) after all API routes. The handler resolves the
requested path inside the dist directory and:

- Returns `FileResponse` for known asset files (`app.js`, `style.css`).
- Returns `HTMLResponse` (index.html) for everything else — client-side hash
  routes, unknown paths, and any path that resolves outside the dist directory
  (traversal attempts).

A `relative_to` guard rejects any resolved path that escapes the dist
directory before serving, so path traversal cannot reach files outside it.

**API routes always take priority.** FastAPI's router matches `/projects` and
`/operations` before the catch-all route is reached, so authenticated API
calls always hit the API layer regardless of whether a static SPA is mounted.

**API-only data access.** The SPA talks exclusively to the odooctl REST API.
It has no direct Docker, Postgres, filesystem, or Python service access.

## Files

```
odooctl/web/
├── __init__.py          Python package init (runner contract hook)
├── README.md            Developer notes
└── dist/
    ├── index.html       SPA entry point
    ├── app.js           Application JavaScript (vanilla, no framework)
    └── style.css        Styles (custom properties + flexbox/grid)
```

Edit `dist/app.js` and `dist/style.css` directly — no build step needed.
Note: `index.html` is read once when the server starts and cached in memory
for the SPA fallback (`odooctl serve` is a long-running process), so changes
to `index.html` require a server restart; `app.js` and `style.css` are served
from disk on each request.

## Running the UI

```bash
# Install API extras
pip install odooctl[api]

# Start server (auto-serves bundled SPA at /)
ODOOCTL_API_KEY=mysecret odooctl serve

# Override with a custom dist directory (for local development)
ODOOCTL_API_KEY=mysecret odooctl serve --static-dir path/to/custom/dist

# Custom port (keep the default localhost-only bind)
ODOOCTL_API_KEY=mysecret odooctl serve --host 127.0.0.1 --port 9000
```

### Reaching the UI from another machine

By default the API binds to `127.0.0.1` **and** `TrustedHostMiddleware` only
accepts `Host: localhost` / `127.0.0.1`, so requests by IP or hostname are
rejected with `Invalid host header`. This localhost lockdown is never removed —
but you can *append* trusted hosts to reach it over a LAN or Tailscale without a
reverse proxy:

```bash
# Bind to all interfaces AND trust the host(s) clients connect to.
ODOOCTL_API_KEY=mysecret odooctl serve \
  --host 0.0.0.0 \
  --allowed-host 192.168.1.50 --allowed-host my-box.tailnet.ts.net

# Equivalent via env var (comma/space separated); '*' trusts any host.
ODOOCTL_ALLOWED_HOSTS="192.168.1.50,my-box.tailnet.ts.net" \
  ODOOCTL_API_KEY=mysecret odooctl serve --host 0.0.0.0
```

If you bind to a non-loopback address **without** any `--allowed-host`, `serve`
prints a warning explaining that remote requests will be rejected.

> **Security:** the server speaks plain HTTP. Token auth still applies to every
> request, but exposing it puts bearer tokens on the wire unencrypted. Prefer an
> encrypted transport (Tailscale, an SSH tunnel, or an authenticating TLS
> reverse proxy) and firewall the port. `--allowed-host` widens the Host
> allowlist; it is not a substitute for transport security.

Open `http://localhost:8787/` (or `http://<allowed-host>:8787/`) and sign in
with your **email and password**. Create the first account on the server:

```bash
odooctl user add you@example.com --role admin
```

Sessions are HttpOnly cookies, revocable via **Sign out**, `odooctl user
disable`, or a password change; see
[Users & access](users-and-access.md).

Alternatively, expand *"Sign in with an API token instead"* and paste a
bearer token (the CLI/CI credential):

```bash
odooctl security token mint \
  --action api --env "*" --project "*" \
  --key-env ODOOCTL_API_KEY \
  --role operator
```

The mint command signs with `ODOOCTL_API_KEY` by default — the same key the
API server verifies with, so the explicit `--key-env` above is optional. See
`docs/rbac.md`.

## Pages

| Hash route | Description |
|---|---|
| `#/` | Dashboard — list all registered projects |
| `#/access` | Access — RBAC role matrix, admin token minting, user accounts |
| `#/project/:name` | Project detail — environment grid, live Containers panel, recent operations |
| `#/project/:name/env/:env` | Environment detail — Overview, Containers, Doctor, Operations, Backups, Restore Points, Clone, Promote, Migrate tabs |

The header shows a **runner status pill** (online/offline), an **Access** link,
and a refresh control, plus the signed-in principal's roles and token expiry.

## Containers panel

The project page (and a per-environment tab) shows live container state for
the project's compose stack — service, state/health, uptime, image — refreshed
every 10 s from the runner's snapshot (`GET /projects/{p}/containers`). If no
runner has probed yet, or the snapshot is stale, the panel says so instead of
showing dead data.

Per service:

- **Logs** (viewer+) enqueues a `service_logs` operation; the runner captures a
  redacted `docker compose logs --tail 200` and streams it into the standard
  log viewer.
- **Restart** (operator+) enqueues `service_restart` behind a typed
  confirmation. Because one compose stack serves every environment of a
  project, restart requires the **admin** role whenever any environment in the
  project is protected — the UI explains this instead of failing server-side.

## Access page (`#/access`)

Shows the full role → action matrix from `GET /rbac/matrix`, with your token's
roles highlighted and protected-only actions marked. Admins additionally get a
**mint token** form (`POST /tokens`): choose role (capped at your own), TTL
(max 7 days), project scope, and a subject label; the token is displayed once
with a copy button and never stored. This is the intended way to hand
teammates viewer/operator access without server shell access.

## Runner status

Enqueuing an operation only writes a queue entry — a separate privileged
[runner](runner-architecture.md) executes it. If no runner is running, queued
operations stay `queued` indefinitely.

To make that legible, the header polls `GET /runner/status` (backed by a
heartbeat the runner writes) and shows a green **Runner online** or red
**Runner offline** pill. When offline, the ops table shows a banner and the log
viewer explains that work will not run until you start one:

```bash
ODOOCTL_API_KEY=mysecret odooctl runner
```

Queued operations can be cancelled from the Operations view (a Cancel action
appears on `queued` rows), which calls `POST /operations/{id}/cancel`.

## RBAC in the UI

The SPA decodes the bearer token payload (base64url, unverified client-side)
to read the `roles` field for **display gating only**. The server always
re-checks RBAC independently. Role mapping:

| Role | Read | Backup/Deploy/Clone/Restore | Admin ops (protected envs, promote) |
|---|---|---|---|
| viewer | ✓ | — | — |
| operator | ✓ | ✓ (non-protected envs) | — |
| admin | ✓ | ✓ | ✓ |
| owner | ✓ | ✓ | ✓ |

Tabs and action buttons are hidden for roles that do not have the required
permission. A viewer sees only the Overview, Operations, and Backups tabs;
Clone and Promote tabs appear only for operator+ (and admin+ respectively).

## Destructive action confirmation

Clone and promote operations show a typed confirmation dialog before
enqueueing. The user must type an exact keyword:

| Operation | Keyword to type |
|---|---|
| Backup | none (confirm button only) |
| Clone a non-protected env | `clone` |
| Clone a protected env | the source environment name (e.g. `production`) |
| Promote | `promote` |

The confirm button remains disabled until the typed value matches the keyword
exactly, then submits via `enqueueOp()` → `POST /projects/{p}/operations`.

## Operation log streaming (SSE)

The SPA streams SSE events from `GET /operations/{id}/events` using `fetch()`
with a `ReadableStream` reader. `EventSource` is not used because it does not
support custom `Authorization` headers in browsers.

The stream reader:

1. Decodes UTF-8 chunks incrementally, splitting on newlines.
2. Parses `data: <json>` SSE lines into event objects.
3. On stream close, fetches the final operation record to display terminal status.

## Runner contract

`odooctl/web/__init__.py` is scanned by `odooctl.security.runner_contract` to
verify no privileged adapter imports are present. The dist JS/CSS files are not
Python and are ignored by the scanner. Run:

```bash
uv run odooctl security runner-check
```

The test `test_web_package_no_privileged_imports` in `tests/test_web.py`
enforces this contract in CI.
