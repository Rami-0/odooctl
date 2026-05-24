from __future__ import annotations
from pathlib import Path

def project_path(path: str | None = None) -> Path:
    return Path(path or ".").resolve()

def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
