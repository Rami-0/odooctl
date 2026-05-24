from __future__ import annotations
import json
from pathlib import Path
from odooctl.metadata.models import BackupManifest, DeploymentMetadata
from odooctl.utils.paths import ensure_dir

class MetadataStore:
    def __init__(self, root: str | Path = ".odooctl"):
        self.root = ensure_dir(root)
        ensure_dir(self.root / "deployments")
        ensure_dir(self.root / "backups")

    def save_deployment(self, metadata: DeploymentMetadata) -> Path:
        path = self.root / "deployments" / f"{metadata.environment}-{metadata.timestamp.replace(':','')}.json"
        path.write_text(metadata.model_dump_json(indent=2))
        (self.root / "deployments" / f"{metadata.environment}-latest.json").write_text(metadata.model_dump_json(indent=2))
        return path

    def save_backup_manifest(self, backup_id: str, manifest: BackupManifest) -> Path:
        path = self.root / "backups" / f"{backup_id}.json"
        path.write_text(manifest.model_dump_json(indent=2))
        (self.root / "backups" / f"{manifest.environment}-latest.json").write_text(manifest.model_dump_json(indent=2))
        return path

    def latest_deployment(self, environment: str) -> dict | None:
        path = self.root / "deployments" / f"{environment}-latest.json"
        return json.loads(path.read_text()) if path.exists() else None

    def latest_backup(self, environment: str) -> dict | None:
        path = self.root / "backups" / f"{environment}-latest.json"
        return json.loads(path.read_text()) if path.exists() else None
