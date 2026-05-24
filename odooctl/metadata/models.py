from __future__ import annotations
from datetime import datetime, timezone
from pydantic import BaseModel, Field


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class BackupManifest(BaseModel):
    project: str
    environment: str
    timestamp: str = Field(default_factory=now_utc)
    db_name: str
    db_dump: str = "db.dump"
    filestore: str = "filestore.tar.zst"
    git_commit: str | None = None
    docker_image: str | None = None
    odoo_version: str
    checksums: dict[str, str] = Field(default_factory=dict)
    status: str = "complete"


class DeploymentMetadata(BaseModel):
    project: str
    environment: str
    timestamp: str = Field(default_factory=now_utc)
    branch: str
    commit: str | None = None
    docker_image: str | None = None
    backup: str | None = None
    modules_updated: list[str] = Field(default_factory=list)
    status: str
    health_check_url: str | None = None
    message: str | None = None
