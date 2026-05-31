"""FastAPI application factory for the odooctl local API.

Create the app with ``create_app(api_key=..., registry_loader=...)`` and
hand it to uvicorn. By default the app binds to localhost-only via
``TrustedHostMiddleware``.

Optional static SPA: pass ``static_dir`` pointing to a pre-built SPA dist
directory and it will be mounted at ``/`` (served as a fallback after API
routes).

No privileged imports — satisfies the runner contract.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from odooctl.api.routes_operations import router as operations_router
from odooctl.api.routes_projects import router as projects_router


def create_app(
    api_key: str,
    *,
    registry_loader: Callable | None = None,
    allowed_hosts: list[str] | None = None,
    static_dir: Path | None = None,
) -> FastAPI:
    """Create and configure the odooctl FastAPI application.

    :param api_key: Shared HMAC key used to verify bearer tokens.
    :param registry_loader: Callable returning a ``Registry``; defaults to
        ``odooctl.registry.load_registry`` so tests can inject a fake.
    :param allowed_hosts: Hosts allowed by ``TrustedHostMiddleware``; defaults
        to ``["127.0.0.1", "localhost"]`` for localhost-only operation.
    :param static_dir: Optional path to a pre-built SPA dist directory mounted
        at ``/`` after all API routes.
    """
    if registry_loader is None:
        from odooctl.registry import load_registry

        registry_loader = load_registry

    app = FastAPI(
        title="odooctl API",
        description="Local management API for self-hosted Odoo deployments.",
        version="1.0.0",
    )

    app.state.api_key = api_key
    app.state.registry_loader = registry_loader

    if allowed_hosts is None:
        allowed_hosts = ["127.0.0.1", "localhost", "testclient"]

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    app.include_router(projects_router)
    app.include_router(operations_router)

    if static_dir is not None and Path(static_dir).exists():
        from fastapi.responses import FileResponse, HTMLResponse

        _static = Path(static_dir).resolve()
        _index = _static / "index.html"

        @app.get("/{full_path:path}", include_in_schema=False)
        async def _spa(full_path: str):
            candidate = (_static / full_path).resolve()
            try:
                candidate.relative_to(_static)
            except ValueError:
                return HTMLResponse(_index.read_text())
            if candidate.is_file():
                return FileResponse(str(candidate))
            return HTMLResponse(_index.read_text())

    return app
