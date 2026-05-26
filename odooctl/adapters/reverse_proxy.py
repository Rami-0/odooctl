from __future__ import annotations

def public_url(domain: str, *, scheme: str = "https", port: int | None = None) -> str:
    if domain.startswith(("http://", "https://")):
        base = domain.rstrip("/")
    else:
        base = f"{scheme}://{domain}"
    if port is None:
        return base
    host = base.rsplit(":", 1)
    if len(host) == 2 and host[1].isdigit():
        return base
    return f"{base}:{port}"
