from __future__ import annotations
import shutil
import tempfile
from pathlib import Path
from odooctl.utils.paths import ensure_dir
from odooctl.utils.shell import run


class FilestoreAdapter:
    def archive(self, filestore_path: str, output: str | Path) -> None:
        source = Path(filestore_path)
        if not source.exists():
            raise FileNotFoundError(f"Filestore path does not exist: {filestore_path}")
        ensure_dir(Path(output).parent)
        run(["tar", "--zstd", "-cf", str(output), "-C", str(source.parent), source.name], stream=True)

    def restore_archive(self, archive_path: str | Path, target_path: str) -> None:
        archive = Path(archive_path)
        if not archive.exists():
            raise FileNotFoundError(f"Filestore archive does not exist: {archive_path}")
        target = Path(target_path)
        ensure_dir(target.parent)
        with tempfile.TemporaryDirectory(dir=target.parent, prefix=f".{target.name}.restore-") as tmpdir:
            run(["tar", "--zstd", "-xf", str(archive), "-C", tmpdir], stream=True)
            extracted = Path(tmpdir) / target.name
            if not extracted.exists():
                children = list(Path(tmpdir).iterdir())
                if len(children) != 1:
                    raise RuntimeError(f"Archive did not contain expected filestore directory: {target.name}")
                extracted = children[0]
            if target.exists():
                shutil.rmtree(target)
            shutil.move(str(extracted), target)

    def copy(self, source: str, target: str) -> None:
        src = Path(source)
        if not src.exists():
            raise FileNotFoundError(f"Source filestore path does not exist: {source}")
        dst = Path(target)
        ensure_dir(dst.parent)
        with tempfile.TemporaryDirectory(dir=dst.parent, prefix=f".{dst.name}.copy-") as tmpdir:
            staged = Path(tmpdir) / dst.name
            shutil.copytree(src, staged)
            if dst.exists():
                shutil.rmtree(dst)
            shutil.move(str(staged), dst)
