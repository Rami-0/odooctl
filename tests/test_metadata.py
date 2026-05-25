from odooctl.metadata.models import BackupManifest, DeploymentMetadata
from odooctl.metadata.store import MetadataStore


def test_backup_manifest_round_trip_includes_artifacts_and_version():
    manifest = BackupManifest(
        backup_id="production_1",
        project="p",
        environment="production",
        db_name="odoo",
        odoo_version="19.0",
        filestore_path="/srv/filestore/odoo",
        artifact_paths=["db.dump", "filestore.tar.zst"],
        checksums={"db.dump": "abc"},
        backup_mode="full",
    )

    data = manifest.model_dump()
    restored = BackupManifest.model_validate(data)

    assert restored.backup_id == "production_1"
    assert restored.schema_version == 1
    assert restored.filestore_path == "/srv/filestore/odoo"
    assert restored.backup_mode == "full"
    assert restored.artifact_paths == ["db.dump", "filestore.tar.zst"]
    assert restored.checksums == {"db.dump": "abc"}


def test_metadata_store_writes_latest_files(tmp_path):
    store = MetadataStore(tmp_path / ".odooctl")
    manifest = BackupManifest(
        backup_id="production_1", project="p", environment="production", db_name="odoo", odoo_version="19.0"
    )
    store.save_backup_manifest("production_1", manifest)
    assert store.latest_backup("production")["db_name"] == "odoo"
    dep = DeploymentMetadata(project="p", environment="staging", branch="staging", status="success")
    store.save_deployment(dep)
    assert store.latest_deployment("staging")["status"] == "success"
