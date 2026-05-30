"""odooctl serve — start the local API server with optional static SPA.

FastAPI and uvicorn must be installed (``pip install odooctl[api]``).
The server binds to 127.0.0.1 by default (localhost-only).
"""
from __future__ import annotations

import os
from pathlib import Path


def run(
    host: str = "127.0.0.1",
    port: int = 8787,
    api_key: str | None = None,
    static_dir: Path | None = None,
    reload: bool = False,
) -> None:
    try:
        import uvicorn  # noqa: F401
        from fastapi import FastAPI  # noqa: F401
    except ImportError:
        raise SystemExit(
            "FastAPI and uvicorn are required for 'odooctl serve'.\n"
            "Install the optional extras: pip install odooctl[api]"
        )

    if api_key is None:
        api_key = os.environ.get("ODOOCTL_API_KEY", "")
    if not api_key:
        raise SystemExit(
            "API key is required. Set --api-key or ODOOCTL_API_KEY env var."
        )

    from odooctl.api.app import create_app

    app = create_app(api_key=api_key, static_dir=static_dir)
    uvicorn.run(app, host=host, port=port, reload=reload)
