# M12 — Local API and Privileged Runner

## Goal

Expose services over an optional local API and execute mutations through a privileged runner.

## Files to create

- `odooctl/api/__init__.py`
- `odooctl/api/app.py`
- `odooctl/api/auth.py`
- `odooctl/api/routes_projects.py`
- `odooctl/api/routes_operations.py`
- `odooctl/api/routes_backups.py`
- `odooctl/api/queue.py`
- `odooctl/runner/__init__.py`
- `odooctl/runner/worker.py`
- `odooctl/commands/serve.py`
- `odooctl/commands/runner.py`
- `docs/api.md`

## API routes

- `GET /projects`
- `GET /projects/{project}`
- `GET /projects/{project}/environments`
- `GET /projects/{project}/environments/{env}`
- `GET /projects/{project}/doctor`
- `GET /projects/{project}/status`
- `POST /projects/{project}/operations`
- `GET /operations/{id}`
- `GET /operations/{id}/events`
- `POST /operations/{id}/cancel`
- `GET /projects/{project}/backups`
- `GET /projects/{project}/audit`

## Commands

- `odooctl serve --host 127.0.0.1 --port 8787`
- `odooctl runner`
- `odooctl runner --once`

## Queue model

- API writes queued operation records.
- Runner claims queued operations under lock.
- Runner executes service operations.
- Events are streamed from operation store.

## Acceptance criteria

- API can list project/environment/status data.
- API can enqueue backup/clone.
- Runner executes queued operation.
- Event streaming works.
- API is localhost-only by default.
- Unauthenticated request fails.
- Viewer token cannot enqueue mutating operation.
