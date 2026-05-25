# Deploy Safety Pipeline Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make `odooctl deploy` safe, observable, and recoverable by adding preflight checks, automatic backups for production, health-gated rollout, and rollback-on-failure behavior.

**Architecture:**
The deploy command should become a small orchestrator that runs a deterministic sequence: load config, resolve environment, run preflight checks, optionally create a backup, deploy via Docker Compose, then verify service and HTTP health. Failures at any stage should produce clear diagnostics and, for production, trigger a rollback path when safe. Keep the implementation mostly inside `odooctl/commands/deploy.py` and supporting adapters/utilities so the CLI surface remains stable.

**Tech Stack:** Python 3.11, Typer, Pydantic, PyYAML, Docker Compose adapter, pytest.

---

### Task 1: Map the existing deploy flow and add a test harness around it

**Objective:** Lock down the current behavior of `deploy` so the refactor is safe.

**Files:**
- Read: `odooctl/commands/deploy.py`
- Read: `tests/test_deploy.py`
- Modify: `tests/test_deploy.py`

**Step 1: Write a test that captures the current happy-path call sequence**

Assert that deploy loads config, resolves the requested environment, and calls the expected adapter methods in order.

**Step 2: Run the deploy test file**

Run: `pytest tests/test_deploy.py -v`

**Expected:** All existing deploy tests pass; the new guard test should initially fail only if it encodes behavior not yet present.

**Step 3: Add only the minimal scaffolding needed to make the test pass**

Do not add new behavior yet.

**Step 4: Re-run the deploy tests**

Run: `pytest tests/test_deploy.py -v`

**Expected:** Pass.

**Step 5: Commit**

```bash
git add tests/test_deploy.py
git commit -m "test: lock down deploy flow"
```

---

### Task 2: Add deploy preflight checks

**Objective:** Prevent known-bad deploys before any state changes occur.

**Files:**
- Modify: `odooctl/commands/deploy.py`
- Modify: `odooctl/config.py` if needed for environment metadata access
- Modify: `odooctl/adapters/postgres.py` if needed for connectivity checks
- Modify: `odooctl/adapters/filestore.py` if needed for path/access checks
- Add or modify: `tests/test_deploy.py`

**Preflight checks to implement:**
- config file exists and validates
- requested environment exists
- branch matches environment policy when configured
- Docker Compose file exists
- target database and filestore paths are reachable or at least structurally valid
- production deploys require explicit confirmation/safe flag if the codebase already uses such a pattern

**Step 1: Write failing tests for each preflight failure mode**

Add focused tests for missing config, missing environment, invalid branch, missing compose file, and inaccessible target paths.

**Step 2: Run the deploy tests and confirm failures are meaningful**

Run: `pytest tests/test_deploy.py -v`

**Expected:** The new tests fail for the right reasons.

**Step 3: Implement the preflight helper(s)**

Add a small helper that returns a structured result or raises a clear exception before deployment starts.

**Step 4: Re-run the deploy tests**

Run: `pytest tests/test_deploy.py -v`

**Expected:** All deploy tests pass.

**Step 5: Commit**

```bash
git add odooctl/commands/deploy.py tests/test_deploy.py odooctl/config.py odooctl/adapters/postgres.py odooctl/adapters/filestore.py
git commit -m "feat: add deploy preflight checks"
```

---

### Task 3: Make production deploys create a backup before rollout

**Objective:** Ensure production changes are always recoverable.

**Files:**
- Modify: `odooctl/commands/deploy.py`
- Modify: `odooctl/commands/backup.py`
- Modify: `tests/test_deploy.py`
- Possibly modify: `tests/test_backup.py`

**Step 1: Add a test that production deploy triggers backup creation first**

Mock the backup command and assert it runs before deployment.

**Step 2: Run the deploy tests**

Run: `pytest tests/test_deploy.py -v`

**Expected:** New test fails until backup orchestration exists.

**Step 3: Implement the production-only backup hook**

For production environments, call backup before any destructive rollout steps.

**Step 4: Re-run the tests**

Run: `pytest tests/test_deploy.py -v`

**Expected:** Pass.

**Step 5: Commit**

```bash
git add odooctl/commands/deploy.py tests/test_deploy.py
git commit -m "feat: back up production before deploy"
```

---

### Task 4: Add post-deploy health verification and rollback-on-failure behavior

**Objective:** Fail unsafe deploys fast and recover automatically when health checks regress.

**Files:**
- Modify: `odooctl/commands/deploy.py`
- Modify: `odooctl/odoo/healthcheck.py`
- Modify: `odooctl/adapters/docker_compose.py`
- Modify: `tests/test_deploy.py`
- Add or modify: `tests/test_healthcheck.py`

**Health checks to include:**
- container/service running state
- Odoo HTTP health endpoint or known readiness probe
- application-specific sanity check if supported
- module update success if deploy includes update steps

**Step 1: Write failing tests for a failed health check path**

Assert that a bad health check causes a non-zero exit and emits a rollback path for production.

**Step 2: Run tests**

Run: `pytest tests/test_deploy.py tests/test_healthcheck.py -v`

**Expected:** Failure until rollback logic exists.

**Step 3: Implement the verification + rollback flow**

If deployment completes but health check fails, roll back code/state where safe and surface a clear error message.

**Step 4: Re-run tests**

Run: `pytest tests/test_deploy.py tests/test_healthcheck.py -v`

**Expected:** Pass.

**Step 5: Commit**

```bash
git add odooctl/commands/deploy.py odooctl/odoo/healthcheck.py odooctl/adapters/docker_compose.py tests/test_deploy.py tests/test_healthcheck.py
git commit -m "feat: verify deploy health and rollback on failure"
```

---

### Task 5: Add deploy progress output and final summary

**Objective:** Make deploys observable for operators.

**Files:**
- Modify: `odooctl/commands/deploy.py`
- Modify: `odooctl/utils/logging.py` if needed
- Modify: `tests/test_deploy.py`

**Step 1: Add a test for progress messages**

Assert the command prints stage markers such as preflight, backup, rollout, verify, done.

**Step 2: Run the deploy tests**

Run: `pytest tests/test_deploy.py -v`

**Expected:** Failure before output formatting is added.

**Step 3: Implement human-readable progress output**

Keep the output concise and deterministic.

**Step 4: Re-run tests**

Run: `pytest tests/test_deploy.py -v`

**Expected:** Pass.

**Step 5: Commit**

```bash
git add odooctl/commands/deploy.py tests/test_deploy.py
git commit -m "feat: add deploy progress reporting"
```

---

### Done criteria

- Deploys refuse obvious bad inputs early
- Production deploys create a backup before rollout
- Health checks gate success
- Production failures attempt rollback when safe
- Operators can see what stage deploy is in
- Tests cover success and failure paths
