"""odooctl serve — start the local API server with optional static SPA.

FastAPI and uvicorn must be installed (``pip install odooctl[api]``).
The server binds to 127.0.0.1 by default (localhost-only).

By default, ``odooctl serve`` automatically serves the packaged SPA from
``odooctl/web/dist/`` at ``/``. Pass ``--static-dir`` to override with a
custom directory (useful during SPA development). The API routes under
``/projects`` and ``/operations`` always take priority over static files.
"""
from __future__ import annotations

import os
from pathlib import Path


def _bundled_dist() -> Path:
    """Return the path to the packaged SPA dist directory bundled with odooctl."""
    return Path(__file__).parent.parent / "web" / "dist"


def _split_hosts(raw: str | None) -> list[str]:
    """Parse a comma/space-separated host list (from ODOOCTL_ALLOWED_HOSTS)."""
    if not raw:
        return []
    return [h.strip() for chunk in raw.split(",") for h in chunk.split() if h.strip()]


def resolve_allowed_hosts(
    cli_hosts: list[str] | None,
    env_value: str | None,
) -> list[str]:
    """Merge --allowed-host values with ODOOCTL_ALLOWED_HOSTS, de-duplicated.

    These are *additional* trusted hosts appended to the localhost-only default;
    the hard localhost lockdown is never removed, only widened when the operator
    explicitly opts in.
    """
    merged: list[str] = []
    for host in [*(cli_hosts or []), *_split_hosts(env_value)]:
        host = host.strip()
        if host and host not in merged:
            merged.append(host)
    return merged


def run(
    host: str = "127.0.0.1",
    port: int = 8787,
    api_key: str | None = None,
    static_dir: Path | None = None,
    reload: bool = False,
    allowed_hosts: list[str] | None = None,
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

    # Auto-detect bundled SPA when no explicit --static-dir is given.
    if static_dir is None:
        bundled = _bundled_dist()
        if bundled.exists():
            static_dir = bundled

    extra_hosts = resolve_allowed_hosts(allowed_hosts, os.environ.get("ODOOCTL_ALLOWED_HOSTS"))

    # Guard against a footgun: binding to a non-loopback interface while the
    # trusted-host allowlist is still localhost-only means every request is
    # rejected with "Invalid host header". Point the operator at the fix.
    if host not in ("127.0.0.1", "localhost", "::1") and not extra_hosts:
        print(
            f"[serve] warning: binding to {host} but the trusted-host allowlist is "
            "localhost-only, so remote requests will be rejected with "
            "'Invalid host header'.\n"
            "        Add the host(s) clients use, e.g. "
            "--allowed-host <ip-or-hostname> (repeatable) or "
            "ODOOCTL_ALLOWED_HOSTS=host1,host2. Use '*' to allow any host "
            "(token auth still applies)."
        )
    if extra_hosts:
        print(f"[serve] trusted hosts (in addition to localhost): {', '.join(extra_hosts)}")

    from odooctl.api.app import create_app

    app = create_app(
        api_key=api_key,
        static_dir=static_dir,
        extra_allowed_hosts=extra_hosts or None,
    )
    uvicorn.run(app, host=host, port=port, reload=reload)
