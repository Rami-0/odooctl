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

> **Warning:** do not bind to a non-loopback address (e.g. `--host 0.0.0.0`).
> The server speaks plain HTTP and is designed for localhost-only operation;
> exposing it puts bearer tokens on the wire unencrypted and lets anyone with
> a token enqueue privileged operations. Use an SSH tunnel (or an
> authenticating TLS reverse proxy plus firewall rules) for remote access.

Open `http://localhost:8787/` and paste an API token. Generate one with:

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
| `#/project/:name` | Project detail — environment grid + recent operations |
| `#/project/:name/env/:env` | Environment detail — Overview, Doctor, Operations, Backups, Clone, Promote tabs |

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
