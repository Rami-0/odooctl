# odooctl Web UI

Vanilla JS single-page application served by `odooctl serve`.

## Architecture

- **No build tooling required.** The `dist/` directory contains hand-authored
  HTML, CSS, and JS that is committed directly and served as-is via a FastAPI
  catch-all route (`GET /{full_path:path}`) using `FileResponse` for known
  assets and `HTMLResponse` (index.html) for all other paths.
- **API-only data access.** The SPA talks exclusively to the odooctl REST API
  (`/projects`, `/operations`, …). It imports nothing from the Python packages
  and has no direct Docker, Postgres, or filesystem access.
- **No Node.js.** Edit `dist/app.js` and `dist/style.css` directly.

## Files

```
odooctl/web/
├── __init__.py          Python package init (runner contract hook)
├── README.md            This file
└── dist/
    ├── index.html       SPA entry point
    ├── app.js           Application JavaScript (vanilla, no framework)
    └── style.css        Styles (custom properties + flexbox/grid)
```

## Running the UI

```bash
# Install API extras
pip install odooctl[api]

# Start server (auto-serves bundled SPA at /)
ODOOCTL_API_KEY=mysecret odooctl serve

# Override with a custom dist directory (for local development)
ODOOCTL_API_KEY=mysecret odooctl serve --static-dir path/to/custom/dist
```

Open `http://localhost:8787/` and paste an API token. Generate one with:

```bash
odooctl security token mint --role operator
```

## Pages

| Hash route | Description |
|---|---|
| `#/` | Dashboard — list all registered projects |
| `#/project/:name` | Project detail — environments + recent operations |
| `#/project/:name/env/:env` | Environment detail — tabs for Overview, Doctor, Operations, Backups, Clone, Promote |

## RBAC in the UI

The SPA decodes the bearer token payload (base64url, unverified) to read the
`roles` field for client-side display gating only. The server always re-checks
RBAC. Role mapping:

| Role | Read | Backup/Deploy/Clone/Restore | Admin ops (protected envs, promote) |
|---|---|---|---|
| viewer | ✓ | — | — |
| operator | ✓ | ✓ (non-protected) | — |
| admin | ✓ | ✓ | ✓ |
| owner | ✓ | ✓ | ✓ |

## Destructive action confirmation

Clone and promote operations show a typed confirmation dialog before enqueueing.
The keyword the user must type:

- **Clone a non-protected env**: type `clone`
- **Clone a protected env**: type the environment name (e.g. `production`)
- **Promote**: type `promote`

## Operation log streaming

The SPA streams SSE events from `GET /operations/{id}/events` using `fetch()`
with a `ReadableStream` reader (instead of `EventSource`, which does not
support custom `Authorization` headers in browsers).

## Runner contract

`odooctl/web/__init__.py` is scanned by `odooctl.security.runner_contract`
to verify no privileged adapter imports are present. The dist JS/CSS files are
not Python and are ignored by the scanner. Run:

```bash
uv run odooctl security runner-check
```
