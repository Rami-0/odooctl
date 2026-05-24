from __future__ import annotations
import shutil
from pathlib import Path
from odooctl.config import RemoteBackupConfig

class S3Adapter:
    def __init__(self, config: RemoteBackupConfig, root: str | Path = ".odooctl/remote-backups"):
        self.config = config
        self.root = Path(root)

    def remote_dir(self) -> Path:
        if not self.config.bucket:
            raise ValueError("remote backup bucket is required")
        return self.root / self.config.bucket

    def upload_backup(self, backup_dir: str | Path) -> Path:
        # MVP fallback: mirror the backup tree locally so the upload path is verifiable
        # without introducing boto3 credentials or network dependencies.
        src = Path(backup_dir)
        dest = self.remote_dir() / src.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        return dest
