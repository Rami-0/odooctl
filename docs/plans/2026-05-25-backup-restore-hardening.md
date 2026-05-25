# Backup and Restore Hardening Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make backups durable, inspectable, and reliably restorable by adding manifests, checksums, retention policies, restore validation, and drill coverage.

**Architecture:**
Treat backup artifacts as first-class objects, not just files on disk. Each backup should carry a manifest describing the environment, timestamp, versions, checksums, and included components. Restore should validate the manifest and artifact integrity before modifying anything. Retention and cleanup should be deterministic and configurable so backup storage stays bounded.

**Tech Stack:** Python 3.11, Pydantic, YAML/JSON manifest files, filesystem adapters, pytest.

---

### Task 1: Define a backup manifest schema

**Objective:** Create a stable metadata format for every backup artifact.

**Files:**
- Modify: `odooctl/metadata/models.py`
- Modify: `odooctl/metadata/store.py`
- Modify: `tests/test_metadata.py`
- Modify: `tests/test_backup.py`

**Manifest fields to include:**
- backup id
- environment name
- project name
- created at timestamp
- database name
- filestore path
- artifact paths
- checksum/hash values
- schema/version marker
- backup mode (full, db-only, filestore-only if supported)

**Step 1: Write tests for manifest creation and round-trip loading**

The manifest should serialize and deserialize without losing fields.

**Step 2: Run metadata and backup tests**

Run: `pytest tests/test_metadata.py tests/test_backup.py -v`

**Expected:** New tests fail until schema exists.

**Step 3: Implement the manifest model and storage helpers**

Add clear types and validation. Keep backwards compatibility if older backups exist.

**Step 4: Re-run tests**

Run: `pytest tests/test_metadata.py tests/test_backup.py -v`

**Expected:** Pass.

**Step 5: Commit**

```bash
git add odooctl/metadata/models.py odooctl/metadata/store.py tests/test_metadata.py tests/test_backup.py
git commit -m "feat: add backup manifest metadata"
```

---

### Task 2: Add checksum generation and artifact verification

**Objective:** Detect corrupted or partial backup artifacts before restore.

**Files:**
- Modify: `odooctl/commands/backup.py`
- Modify: `odooctl/commands/restore.py`
- Modify: `odooctl/adapters/filestore.py`
- Modify: `tests/test_backup.py`
- Modify: `tests/test_restore.py`

**Step 1: Add checksum-focused tests**

Assert that backup writes a checksum and restore validates it.

**Step 2: Run the backup/restore tests**

Run: `pytest tests/test_backup.py tests/test_restore.py -v`

**Expected:** Failure until integrity verification exists.

**Step 3: Implement checksum generation and verification helpers**

Use a deterministic hash over backup artifacts and manifest entries.

**Step 4: Re-run tests**

Run: `pytest tests/test_backup.py tests/test_restore.py -v`

**Expected:** Pass.

**Step 5: Commit**

```bash
git add odooctl/commands/backup.py odooctl/commands/restore.py odooctl/adapters/filestore.py tests/test_backup.py tests/test_restore.py
git commit -m "feat: verify backup integrity with checksums"
```

---

### Task 3: Add retention policy and cleanup behavior

**Objective:** Prevent backup sprawl while keeping recent restore points.

**Files:**
- Modify: `odooctl/commands/backup.py`
- Modify: `odooctl/config.py`
- Modify: `tests/test_backup.py`

**Retention policy options to support:**
- keep last N backups per environment
- keep backups newer than X days
- optional archive-only policy if already supported elsewhere

**Step 1: Write tests for retention pruning**

Ensure old backups are deleted according to policy and recent ones remain.

**Step 2: Run the backup tests**

Run: `pytest tests/test_backup.py -v`

**Expected:** Fails until pruning exists.

**Step 3: Implement retention cleanup**

Apply pruning only after a successful backup by default.

**Step 4: Re-run tests**

Run: `pytest tests/test_backup.py -v`

**Expected:** Pass.

**Step 5: Commit**

```bash
git add odooctl/commands/backup.py odooctl/config.py tests/test_backup.py
git commit -m "feat: add backup retention policy"
```

---

### Task 4: Make restore validate manifests before mutating state

**Objective:** Avoid restoring from invalid or incompatible artifacts.

**Files:**
- Modify: `odooctl/commands/restore.py`
- Modify: `odooctl/metadata/store.py`
- Modify: `tests/test_restore.py`

**Validation rules to enforce:**
- backup exists
- manifest exists
- checksums match
- target environment is compatible with source backup
- restore mode is supported by the artifact

**Step 1: Add tests for invalid restore inputs**

Cover missing manifest, checksum mismatch, and environment mismatch.

**Step 2: Run restore tests**

Run: `pytest tests/test_restore.py -v`

**Expected:** Failures until validation is implemented.

**Step 3: Implement restore gating**

Restore must validate first, then mutate.

**Step 4: Re-run tests**

Run: `pytest tests/test_restore.py -v`

**Expected:** Pass.

**Step 5: Commit**

```bash
git add odooctl/commands/restore.py odooctl/metadata/store.py tests/test_restore.py
git commit -m "feat: validate restore artifacts before use"
```

---

### Task 5: Add restore drill and smoke coverage

**Objective:** Prove backups can actually restore successfully.

**Files:**
- Modify: `tests/test_restore.py`
- Modify: `tests/test_backup.py`
- Optionally add: `tests/test_cli_smoke.py`

**Step 1: Add a drill-style test using fixture artifacts**

The test should simulate a successful backup and restore cycle with a temporary filesystem.

**Step 2: Run the test suite for backup and restore**

Run: `pytest tests/test_backup.py tests/test_restore.py -v`

**Expected:** Pass after implementation.

**Step 3: Keep the smoke test lightweight**

Focus on orchestration and verification, not real external services.

**Step 4: Re-run all relevant tests**

Run: `pytest tests/test_backup.py tests/test_restore.py tests/test_cli_smoke.py -v`

**Expected:** Pass.

**Step 5: Commit**

```bash
git add tests/test_backup.py tests/test_restore.py tests/test_cli_smoke.py
git commit -m "test: add backup and restore drill coverage"
```

---

### Done criteria

- Every backup writes a manifest
- Backups include integrity verification
- Retention keeps storage bounded
- Restore validates before mutating anything
- There is test coverage for a realistic backup/restore path
