from __future__ import annotations

import os
import shutil
from pathlib import Path, PurePosixPath
from typing import Any

from rich.console import Console

from odooctl.config import RemoteBackupConfig


class S3Adapter:
    def __init__(
        self,
        config: RemoteBackupConfig,
        root: str | Path = ".odooctl/remote-backups",
        *,
        console: Console | None = None,
        boto3_module: Any | None = None,
    ):
        self.config = config
        self.root = Path(root)
        self.console = console or Console(stderr=True)
        self._boto3 = boto3_module

    def remote_dir(self) -> Path:
        if not self.config.bucket:
            raise ValueError("remote backup bucket is required")
        return self.root / self.config.bucket

    def _warn(self, message: str) -> None:
        self.console.print(f"[yellow]Warning:[/] {message}")

    def _load_boto3(self) -> Any | None:
        if self._boto3 is not None:
            return self._boto3
        try:
            import boto3  # type: ignore[import-not-found]
        except ImportError:
            return None
        return boto3

    def _region(self) -> str | None:
        if self.config.region_env and os.getenv(self.config.region_env):
            return os.getenv(self.config.region_env)
        return self.config.region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")

    def _endpoint_url(self) -> str | None:
        return os.getenv(self.config.endpoint_env) if self.config.endpoint_env else None

    def _credentials(self) -> dict[str, str]:
        credentials: dict[str, str] = {}
        if self.config.access_key_env and os.getenv(self.config.access_key_env):
            credentials["aws_access_key_id"] = os.getenv(self.config.access_key_env, "")
        if self.config.secret_key_env and os.getenv(self.config.secret_key_env):
            credentials["aws_secret_access_key"] = os.getenv(self.config.secret_key_env, "")
        return credentials

    def _object_key(self, backup_name: str, relative_path: Path) -> str:
        base = PurePosixPath(self.config.prefix.strip("/")) if self.config.prefix else PurePosixPath("")
        return str(base / backup_name / relative_path.as_posix()).lstrip("/")

    def _mirror_locally(self, backup_dir: str | Path) -> Path:
        src = Path(backup_dir)
        dest = self.remote_dir() / src.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        return dest

    def _upload_with_boto3(self, backup_dir: Path, boto3_module: Any) -> str:
        if not self.config.bucket:
            raise ValueError("remote backup bucket is required")
        endpoint_url = self._endpoint_url()
        client_kwargs: dict[str, Any] = {**self._credentials()}
        region = self._region()
        if region:
            client_kwargs["region_name"] = region
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url
        client = boto3_module.client("s3", **client_kwargs)
        for file_path in sorted(path for path in backup_dir.rglob("*") if path.is_file()):
            key = self._object_key(backup_dir.name, file_path.relative_to(backup_dir))
            client.upload_file(str(file_path), self.config.bucket, key)
        prefix = self._object_key(backup_dir.name, Path(""))
        return f"s3://{self.config.bucket}/{prefix}".rstrip("/")

    def upload_backup(self, backup_dir: str | Path) -> Path | str:
        src = Path(backup_dir)
        boto3_module = self._load_boto3()
        if boto3_module is None:
            self._warn("boto3 is not installed; mirroring remote backup locally instead")
            return self._mirror_locally(src)
        try:
            return self._upload_with_boto3(src, boto3_module)
        except Exception as exc:  # pragma: no cover - exercised by unit tests with injected client failures
            self._warn(f"S3 upload failed ({exc}); mirroring remote backup locally instead")
            return self._mirror_locally(src)
