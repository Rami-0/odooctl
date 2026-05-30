# Odoo 19 Community staging experiment — M7 live fixture verification

Date: 2026-05-30
Agent/model: Claw via Hermes, OpenAI Codex GPT-5.4
Repo: `/home/dev/odooctl`
Commit under test: `280fea7`
Experiment fixture: `experiments/odoo19-community-staging`

## Purpose

Close the remaining M7 blocker by proving, on the real Odoo 19 Docker fixture, that live mutating commands emit operation events and append a valid audit chain.

## Repo gates passed

```bash
uv run pytest -q
# 210 passed

uv run ruff check .
# All checks passed

uv run python -m build
# Successfully built odooctl-0.1.0.tar.gz and odooctl-0.1.0-py3-none-any.whl
```

## Fixture commands run

Commands were run from `experiments/odoo19-community-staging` with `ODOO_DB_PASSWORD=odoo`.

```bash
docker compose up -d
uv run python -m odooctl validate --config odooctl.yml
uv run python -m odooctl doctor --config odooctl.yml
uv run python -m odooctl status --environment production --config odooctl.yml --json-output
uv run python -m odooctl backup production --config odooctl.yml
uv run python -m odooctl restore production --backup production_2026-05-30_170604 --config odooctl.yml
uv run python -m odooctl clone production staging --sanitize --config odooctl.yml
uv run python -m odooctl update-modules staging --modules base --config odooctl.yml
curl -I 'http://localhost:18069/web/login?db=odoo_staging'
docker compose exec -T db psql -U odoo -d odoo_staging -At -c 'select current_database(), count(*) from ir_module_module;'
```

## Results

### Config / doctor / status

- `validate` passed.
- `doctor` passed.
- `status --json-output` reported:
  - `current_git_commit`: `280fea7`
  - production URL: `http://localhost:18069`
  - production health URL: `http://localhost:18069/web/login?db=odoo_prod`

### Real mutating operations passed

- Backup succeeded: `production_2026-05-30_170604`
- Restore succeeded from that backup.
- Clone `production -> staging --sanitize` succeeded.
- `update-modules staging --modules base` succeeded.
- HTTP login check returned `302 FOUND` for `http://localhost:18069/web/login?db=odoo_staging`.
- Database verification returned: `odoo_staging|695`.

## Operation/event/audit evidence

State directory: `experiments/odoo19-community-staging/.odooctl`

### Successful operation records

- Backup op: `f2df29f37630`
- Restore op: `86597b4ed392`
- Clone op: `8e025a94cfd4`
- Update-modules op: `dcd769739a69`

Each operation produced both:
- `operations/<op_id>/operation.json`
- `operations/<op_id>/events.jsonl`

Observed event examples:

- Backup events include `operation started`, `starting backup`, `backup complete: production_2026-05-30_170604`, `operation completed`.
- Clone events include `operation started: clone on staging`, `cloning production → staging`, `clone complete: http://localhost:18069`, `operation completed`.

### Audit chain verification

Audit file: `experiments/odoo19-community-staging/.odooctl/audit.jsonl`

Observed successful tail entries:
- `backup production succeeded f2df29f37630`
- `restore production succeeded 86597b4ed392`
- `clone staging succeeded 8e025a94cfd4`
- `update_modules staging succeeded dcd769739a69`

Local verification script result:

```text
entries= 5
verify_chain= True
```

That confirms the live fixture run appended audit entries with intact `prev_hash -> current_hash` continuity.

## Extra failure-path evidence

Before the stack was started, a backup attempt failed because the Compose `db` service was not running.

- Failed op: `8273797c6b77`
- `operation.json` recorded status `failed` with the exact Docker error.
- `events.jsonl` recorded the error path and final `operation failed` event.
- The failed audit entry also chained correctly into the later successful entries.

This is useful because it shows the lock/error-path audit/event behavior is present on the real fixture too, not only in unit tests.

## Conclusion

M7 live fixture verification passed.

The remaining blocker is cleared:
- real backup emits operation events and audit entries
- real restore emits operation events and audit entries
- real clone emits operation events and audit entries
- real update-modules emits operation events and audit entries
- audit chain verifies successfully after the live run

M7 can proceed to review gate / closeout and M8 is no longer blocked on missing live-fixture evidence.
