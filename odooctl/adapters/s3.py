from __future__ import annotations
from pathlib import Path

class S3Adapter:
    def upload_backup(self, backup_dir: str | Path) -> None:
        # Placeholder for boto3/rclone integration. Local backups are functional in MVP.
        raise NotImplementedError("Remote S3 upload is planned after the local-backup MVP")
