"""Read-only Docker Compose detector for existing Odoo deployments.

Safety contract (non-negotiable):
  - MUST NOT run any subprocess or shell commands.
  - MUST NOT write any files.
  - MUST NOT restart, stop, or start containers.
  - MUST NOT access the Docker daemon.
  - MUST NOT inline secret values in returned data structures.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from odooctl.importer.models import DetectedCompose

# Env keys that are considered secret — their values must never be inlined.
_SECRET_KEYS = frozenset({"PASSWORD", "SECRET", "KEY", "TOKEN", "PASS"})


def _is_secret_key(key: str) -> bool:
    upper = key.upper()
    return any(tok in upper for tok in _SECRET_KEYS)


def _extract_env_var_name(value: str) -> str | None:
    """Return the env-var name from a ${VAR:-default} or $VAR interpolation.

    Returns None if the value is not an interpolation expression.
    """
    s = str(value)
    m = re.match(r"\$\{([A-Z_][A-Z0-9_]*)(?:[^}]*)?\}", s)
    if m:
        return m.group(1)
    m = re.match(r"\$([A-Z_][A-Z0-9_]*)\s*$", s)
    if m:
        return m.group(1)
    return None


def _parse_env(raw: Any) -> dict[str, str]:
    """Normalise compose environment (dict or list form) to a str→str dict."""
    if isinstance(raw, dict):
        return {str(k): str(v) if v is not None else "" for k, v in raw.items()}
    if isinstance(raw, list):
        result: dict[str, str] = {}
        for item in raw:
            if "=" in str(item):
                k, v = str(item).split("=", 1)
                result[k.strip()] = v.strip()
        return result
    return {}


def detect_from_compose(compose_path: Path) -> DetectedCompose:
    """Parse a docker-compose.yml and return a DetectedCompose snapshot.

    This function is purely read-only: it only reads the compose file.
    No Docker daemon access, no subprocess calls, no file writes.
    """
    data = yaml.safe_load(compose_path.read_text())
    services: dict[str, Any] = data.get("services", {})

    # --- Identify Odoo and Postgres services by image heuristic ---
    odoo_service: str | None = None
    odoo_image: str = ""
    postgres_service: str | None = None
    postgres_image: str = ""

    for name, svc in services.items():
        image = svc.get("image", "")
        img_lower = image.lower()
        if "odoo" in img_lower and odoo_service is None:
            odoo_service = name
            odoo_image = image
        if ("postgres" in img_lower or "postgresql" in img_lower) and postgres_service is None:
            postgres_service = name
            postgres_image = image

    if odoo_service is None:
        raise ValueError(
            "No Odoo service detected in compose file. "
            "Ensure at least one service uses an image that contains 'odoo'."
        )

    odoo_svc = services[odoo_service]
    odoo_env = _parse_env(odoo_svc.get("environment", {}))

    # --- HTTP port ---
    http_port: int | None = None
    for port_entry in odoo_svc.get("ports", []):
        port_str = str(port_entry)
        # Handles "HOST:CONTAINER" and integer forms
        parts = port_str.split(":")
        try:
            if len(parts) == 2:
                container_port = int(parts[1])
                if container_port == 8069:
                    http_port = int(parts[0])
            elif len(parts) == 1:
                if int(parts[0]) == 8069:
                    http_port = 8069
        except ValueError:
            pass

    # --- DB connection details from Odoo service environment ---
    db_host: str | None = None
    db_user: str | None = None
    db_password_ref: str | None = None

    _HOST_KEYS = {"HOST", "DB_HOST", "PGHOST", "ODOO_HOST"}
    _USER_KEYS = {"USER", "DB_USER", "PGUSER", "ODOO_USER"}
    _PASS_KEYS = {"PASSWORD", "DB_PASSWORD", "PGPASSWORD", "ODOO_PASSWORD"}

    for key, value in odoo_env.items():
        upper = key.upper()
        if upper in _HOST_KEYS and db_host is None:
            db_host = value
        elif upper in _USER_KEYS and db_user is None:
            db_user = value
        elif upper in _PASS_KEYS and db_password_ref is None:
            ref = _extract_env_var_name(value)
            if ref:
                db_password_ref = ref
            else:
                # Value is a literal (not a reference). We refuse to store it;
                # record a fallback reference name so config generation is safe.
                db_password_ref = "ODOO_DB_PASSWORD"

    # --- Volumes: filestore + addons ---
    filestore_volume: str | None = None
    filestore_path: str = "/var/lib/odoo"
    addons_paths: list[str] = []

    for vol in odoo_svc.get("volumes", []):
        parts = str(vol).split(":")
        if len(parts) < 2:
            continue
        source, target = parts[0], parts[1]
        if target == "/var/lib/odoo":
            # Named volume (not a bind mount)
            if not source.startswith(".") and not source.startswith("/"):
                filestore_volume = source
            filestore_path = target
        elif any(tok in target for tok in ("/addons", "/extra-addons", "/custom-addons")):
            addons_paths.append(target)

    # --- DB name candidates from Postgres service ---
    db_name_candidates: list[str] = []
    if postgres_service:
        pg_env = _parse_env(services[postgres_service].get("environment", {}))
        for pg_key in ("POSTGRES_DB", "PGDATABASE"):
            val = pg_env.get(pg_key, "")
            if val and not val.startswith("$"):
                db_name_candidates.append(val)

    return DetectedCompose(
        compose_path=compose_path,
        odoo_service=odoo_service,
        odoo_image=odoo_image,
        postgres_service=postgres_service or "",
        postgres_image=postgres_image,
        http_port=http_port,
        db_host=db_host,
        db_user=db_user,
        db_password_ref=db_password_ref,
        db_name_candidates=db_name_candidates,
        addons_paths=addons_paths,
        filestore_volume=filestore_volume,
        filestore_path=filestore_path,
        odoo_conf_settings={},
        workers=None,
        proxy_mode=None,
        dbfilter=None,
    )
