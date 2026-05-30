"""odooctl catalog — declarative stack, addon, and companion service catalog."""
from odooctl.catalog.schema import (
    AddonPack,
    AddonSource,
    CatalogEntry,
    CompanionService,
    StackTemplate,
)
from odooctl.catalog.registry import get_entry, get_stack_templates, list_entries, load_manifest

__all__ = [
    "AddonPack",
    "AddonSource",
    "CatalogEntry",
    "CompanionService",
    "StackTemplate",
    "get_entry",
    "get_stack_templates",
    "list_entries",
    "load_manifest",
]
