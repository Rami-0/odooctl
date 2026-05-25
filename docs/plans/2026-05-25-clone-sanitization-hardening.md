# Clone and Sanitization Hardening Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make production-to-staging cloning safer and more useful by expanding sanitization, adding explicit clone previews, and verifying cloned environments with smoke checks.

**Architecture:**
Clone should be a controlled workflow: identify source and target environments, create the clone, run sanitization according to a named profile, rewrite environment-specific settings, and verify the target is usable. The sanitization rules should be explicit and testable so teams can choose how aggressive the data scrub should be. The end result should be a staging environment that is safe for internal use without leaking production-only data or integrations.

**Tech Stack:** Python 3.11, Odoo sanitization helpers, Docker Compose adapter, pytest, Pydantic.

---

### Task 1: Audit and document current sanitization behavior

**Objective:** Freeze the current sanitization contract before expanding it.

**Files:**
- Read: `odooctl/odoo/sanitize.py`
- Read: `tests/test_sanitize.py`
- Read: `odooctl/commands/clone.py`
- Modify: `tests/test_sanitize.py`

**Step 1: Add tests that describe the current scrub rules**

Capture what is already sanitized so new profiles don’t break it accidentally.

**Step 2: Run the sanitize tests**

Run: `pytest tests/test_sanitize.py -v`

**Expected:** Existing behavior remains green; new guard tests reveal gaps if any.

**Step 3: Tighten the sanitization contract in code if needed**

Do not expand scope yet.

**Step 4: Re-run tests**

Run: `pytest tests/test_sanitize.py -v`

**Expected:** Pass.

**Step 5: Commit**

```bash
git add tests/test_sanitize.py
git commit -m "test: document current sanitization behavior"
```

---

### Task 2: Add named sanitization profiles

**Objective:** Allow different scrub strength levels for different clone use cases.

**Files:**
- Modify: `odooctl/odoo/sanitize.py`
- Modify: `odooctl/commands/clone.py`
- Modify: `odooctl/config.py` if needed
- Modify: `tests/test_sanitize.py`
- Modify: `tests/test_clone.py`

**Profiles to support:**
- `strict` — heavy scrub, safest for broad sharing
- `normal` — default staging scrub
- `minimal` — keep more data for internal QA, still removes dangerous integrations

**Step 1: Write failing tests for profile selection**

Assert the clone command accepts a profile and routes to the correct sanitization rules.

**Step 2: Run clone and sanitize tests**

Run: `pytest tests/test_sanitize.py tests/test_clone.py -v`

**Expected:** Fail until profile routing exists.

**Step 3: Implement profile-aware sanitization**

Keep rules explicit and easy to review.

**Step 4: Re-run tests**

Run: `pytest tests/test_sanitize.py tests/test_clone.py -v`

**Expected:** Pass.

**Step 5: Commit**

```bash
git add odooctl/odoo/sanitize.py odooctl/commands/clone.py tests/test_sanitize.py tests/test_clone.py
git commit -m "feat: add sanitization profiles"
```

---

### Task 3: Add a clone preview / dry-run summary

**Objective:** Show exactly what will happen before modifying data.

**Files:**
- Modify: `odooctl/commands/clone.py`
- Modify: `tests/test_clone.py`

**Preview should include:**
- source environment
- target environment
- sanitization profile
- base URL rewrite target
- scheduled jobs/integrations affected
- whether production source is allowed

**Step 1: Add a dry-run test for clone preview output**

The preview should be readable and deterministic.

**Step 2: Run clone tests**

Run: `pytest tests/test_clone.py -v`

**Expected:** New preview test fails until implemented.

**Step 3: Implement preview mode**

No external changes in dry-run mode.

**Step 4: Re-run tests**

Run: `pytest tests/test_clone.py -v`

**Expected:** Pass.

**Step 5: Commit**

```bash
git add odooctl/commands/clone.py tests/test_clone.py
git commit -m "feat: add clone preview output"
```

---

### Task 4: Expand sanitization coverage for risky integrations and scheduled jobs

**Objective:** Reduce the chance that staging clones send emails, call payment providers, or run dangerous automation.

**Files:**
- Modify: `odooctl/odoo/sanitize.py`
- Modify: `tests/test_sanitize.py`

**Rules to cover:**
- outbound email and mail servers
- payment providers and checkout hooks
- webhooks / API callbacks
- cron jobs and scheduled actions
- base URL and environment-specific secrets

**Step 1: Write tests for each new scrub rule**

Each rule should have a focused assertion.

**Step 2: Run sanitize tests**

Run: `pytest tests/test_sanitize.py -v`

**Expected:** Fail until all rules exist.

**Step 3: Implement the new scrub rules**

Keep behavior conservative by default.

**Step 4: Re-run tests**

Run: `pytest tests/test_sanitize.py -v`

**Expected:** Pass.

**Step 5: Commit**

```bash
git add odooctl/odoo/sanitize.py tests/test_sanitize.py
git commit -m "feat: expand clone sanitization coverage"
```

---

### Task 5: Add clone verification smoke checks

**Objective:** Confirm the cloned staging environment is actually usable.

**Files:**
- Modify: `odooctl/commands/clone.py`
- Modify: `odooctl/odoo/healthcheck.py`
- Modify: `tests/test_clone.py`
- Possibly modify: `tests/test_healthcheck.py`

**Verification should check:**
- target container is running
- sanitized base URL is applied
- Odoo responds on the expected endpoint
- clone command returns a useful staging URL

**Step 1: Add a test for post-clone verification**

The clone flow should fail clearly when the target is not healthy.

**Step 2: Run clone and health tests**

Run: `pytest tests/test_clone.py tests/test_healthcheck.py -v`

**Expected:** Fail until verification is wired in.

**Step 3: Implement the verification step**

Keep it small and reusable.

**Step 4: Re-run tests**

Run: `pytest tests/test_clone.py tests/test_healthcheck.py -v`

**Expected:** Pass.

**Step 5: Commit**

```bash
git add odooctl/commands/clone.py odooctl/odoo/healthcheck.py tests/test_clone.py tests/test_healthcheck.py
git commit -m "feat: verify cloned staging environments"
```

---

### Done criteria

- Clone supports explicit sanitization profiles
- Dry-run preview shows what will change
- Risky integrations and scheduled actions are scrubbed
- Clone verification confirms the target is usable
- Tests cover sanitization and clone behavior
