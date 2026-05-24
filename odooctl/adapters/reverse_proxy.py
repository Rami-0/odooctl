from __future__ import annotations

def public_url(domain: str) -> str:
    if domain.startswith(("http://", "https://")):
        return domain
    return f"https://{domain}"
