from pathlib import Path

from odooctl.adapters import filestore as filestore_module
from odooctl.adapters.filestore import DockerVolumeFilestore, FilestoreAdapter, make_filestore_adapter
from odooctl.context import ProjectContext


CONFIG = """project:
  name: demo
  odoo_version: "19.0"
runtime:
  compose_file: docker-compose.yml
  execution_mode: docker
postgres:
  service: db
  user: odoo
odoo:
  image: odoo:19.0
  service: odoo
  filestore_container_path: /var/lib/odoo
environments:
  staging:
    branch: staging
    domain: staging.example.com
    db_name: odoo_staging
    filestore_path: odoo_staging
    filestore_volume: odoo-data
"""


class DummyCompose:
    def __init__(self, compose_file: str, project_dir: str | None = None):
        self.compose_file = compose_file
        self.project_dir = project_dir
        self.calls = []

    def exec_capture_bytes(self, service, args, *, stdout_path):
        self.calls.append(("capture", service, args, Path(stdout_path)))

    def exec_pipe_stdin(self, service, args, *, stdin_path):
        self.calls.append(("stdin", service, args, Path(stdin_path)))

    def exec(self, service, args, *, stream=True):
        self.calls.append(("exec", service, args, stream))


def context(tmp_path: Path) -> ProjectContext:
    (tmp_path / "odooctl.yml").write_text(CONFIG)
    return ProjectContext.from_config_path(tmp_path / "odooctl.yml")


def test_make_filestore_adapter_selects_docker_volume_backend(tmp_path: Path, monkeypatch):
    ctx = context(tmp_path)
    created = []

    def factory(compose_file: str, project_dir: str | None = None):
        compose = DummyCompose(compose_file, project_dir)
        created.append(compose)
        return compose

    monkeypatch.setattr(filestore_module, "DockerComposeAdapter", factory)

    adapter = make_filestore_adapter(ctx, ctx.config.env("staging"))

    assert isinstance(adapter, DockerVolumeFilestore)
    assert created[0].compose_file == "docker-compose.yml"
    assert created[0].project_dir == str(tmp_path)


def test_host_filestore_uses_plain_tar_archive(tmp_path: Path, monkeypatch):
    source = tmp_path / "filestore" / "odoo_staging"
    source.mkdir(parents=True)
    archive = tmp_path / "backups" / "filestore.tar"
    target = tmp_path / "restored" / "odoo_staging"
    archive.parent.mkdir()
    target.parent.mkdir()
    archive.write_bytes(b"tar")
    calls = []

    def fake_run(args, *, stream=True):
        calls.append((args, stream))
        if args[:2] == ["tar", "-xf"]:
            extracted = Path(args[-1]) / "odoo_staging"
            extracted.mkdir()

    monkeypatch.setattr(filestore_module, "run", fake_run)

    adapter = FilestoreAdapter()
    adapter.archive(str(source), archive)
    adapter.restore_archive(archive, str(target))

    assert calls[0] == (["tar", "-cf", str(archive), "-C", str(source.parent), source.name], True)
    assert calls[1][0][:3] == ["tar", "-xf", str(archive)]
    assert calls[1][0][3] == "-C"
    assert calls[1][1] is True
    assert "--zstd" not in calls[0][0]
    assert "--zstd" not in calls[1][0]


def test_docker_volume_filestore_streams_archive_restore_and_copy(tmp_path: Path, monkeypatch):
    ctx = context(tmp_path)
    compose = DummyCompose("docker-compose.yml", str(tmp_path))
    monkeypatch.setattr(filestore_module, "DockerComposeAdapter", lambda *args, **kwargs: compose)
    adapter = DockerVolumeFilestore(ctx, ctx.config)

    adapter.archive("odoo_staging", tmp_path / "filestore.tar")
    adapter.restore_archive(tmp_path / "filestore.tar", "odoo_staging")
    adapter.copy("odoo_prod", "odoo_staging")

    assert compose.calls[0] == (
        "capture",
        "odoo",
        ["tar", "-cf", "-", "-C", "/var/lib/odoo/filestore", "odoo_staging"],
        tmp_path / "filestore.tar",
    )
    assert compose.calls[1][0:3] == (
        "exec",
        "odoo",
        ["sh", "-lc", "mkdir -p /var/lib/odoo/filestore && rm -rf /var/lib/odoo/filestore/odoo_staging"],
    )
    assert compose.calls[2] == (
        "stdin",
        "odoo",
        ["tar", "-xf", "-", "-C", "/var/lib/odoo/filestore"],
        tmp_path / "filestore.tar",
    )
    assert compose.calls[3][0:3] == (
        "exec",
        "odoo",
        [
            "sh",
            "-lc",
            "mkdir -p /var/lib/odoo/filestore && rm -rf /var/lib/odoo/filestore/odoo_staging && cp -a /var/lib/odoo/filestore/odoo_prod /var/lib/odoo/filestore/odoo_staging",
        ],
    )
