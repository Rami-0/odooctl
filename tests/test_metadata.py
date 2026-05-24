from odooctl.metadata.models import BackupManifest, DeploymentMetadata
from odooctl.metadata.store import MetadataStore

def test_metadata_store_writes_latest_files(tmp_path):
    store = MetadataStore(tmp_path / ".odooctl")
    manifest = BackupManifest(project="p", environment="production", db_name="odoo", odoo_version="19.0")
    store.save_backup_manifest("production_1", manifest)
    assert store.latest_backup("production")["db_name"] == "odoo"
    dep = DeploymentMetadata(project="p", environment="staging", branch="staging", status="success")
    store.save_deployment(dep)
    assert store.latest_deployment("staging")["status"] == "success"
