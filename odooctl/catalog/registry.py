"""Catalog registry: load bundled and user manifests, list and look up entries."""
from __future__ import annotations

from pathlib import Path

import yaml

from odooctl.catalog.schema import (
    AddonPack,
    AddonSource,
    CatalogEntry,
    CompanionService,
    StackTemplate,
)

_MANIFEST_DIR = Path(__file__).parent / "manifests"

_KIND_MAP: dict[str, type] = {
    "StackTemplate": StackTemplate,
    "AddonSource": AddonSource,
    "AddonPack": AddonPack,
    "CompanionService": CompanionService,
}


def _parse_entry(raw: dict) -> CatalogEntry:
    kind = raw.get("kind")
    cls = _KIND_MAP.get(kind)  # type: ignore[arg-type]
    if cls is None:
        raise ValueError(f"Unknown catalog entry kind: {kind!r}")
    return cls.model_validate(raw)


def load_manifest(path: Path) -> list[CatalogEntry]:
    """Parse a YAML manifest file and return typed catalog entries.

    Accepts a YAML file whose top-level value is either a single entry dict or
    a list of entry dicts.
    """
    raw = yaml.safe_load(path.read_text())
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        raise ValueError(
            f"Manifest must be a YAML list or mapping, got {type(raw).__name__}: {path}"
        )
    return [_parse_entry(entry) for entry in raw]


def _load_bundled() -> list[CatalogEntry]:
    entries: list[CatalogEntry] = []
    for manifest_path in sorted(_MANIFEST_DIR.glob("*.yaml")):
        entries.extend(load_manifest(manifest_path))
    return entries


# Loaded once at import time; covers all bundled manifests.
_BUNDLED: list[CatalogEntry] = _load_bundled()


def list_entries(extra: list[CatalogEntry] | None = None) -> list[CatalogEntry]:
    """Return all catalog entries: bundled manifests followed by any extras."""
    return list(_BUNDLED) + list(extra or [])


def get_entry(id: str, extra: list[CatalogEntry] | None = None) -> CatalogEntry | None:
    """Look up a catalog entry by ID. Returns None if not found."""
    for entry in list_entries(extra):
        if entry.id == id:
            return entry
    return None


def get_stack_templates(extra: list[CatalogEntry] | None = None) -> dict[str, StackTemplate]:
    """Return all StackTemplate entries keyed by ID."""
    return {
        e.id: e
        for e in list_entries(extra)
        if isinstance(e, StackTemplate)
    }
