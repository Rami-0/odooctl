# Migration and Upgrade Assistant

`odooctl` provides safe Odoo version upgrade rehearsal and readiness reporting.
The goal is evidence and rehearsal, not one-click blind production upgrade.

## Commands

### `odooctl migrate matrix`

Print the supported Odoo upgrade paths:

```
odooctl migrate matrix
```

Output shows each supported `from → to` path, whether OpenUpgrade is required,
and notes on the recommended tooling.  Only adjacent-version upgrades (N → N+1)
are listed; multi-version jumps require sequential hops.

### `odooctl migrate scan --env <env> --to <version>`

Scan installed modules in an environment for upgrade readiness:

```
odooctl migrate scan --env production --to 18.0
```

Reports:
- Total count of installed modules
- **Blockers** — issues that must be resolved before upgrading (e.g. multi-version jumps)
- **Warnings** — items requiring manual review (custom modules, known-sensitive modules)

Exit code 1 if any blockers are found.

### `odooctl migrate rehearse --env <env> --to <version>`

Run a full upgrade rehearsal.  Production DB and filestore are **never modified**.

```
odooctl migrate rehearse --env production --to 18.0
```

With OpenUpgrade (OCA):

```
odooctl migrate rehearse --env production --to 18.0 --openupgrade
```

Keep the throwaway DB for debugging:

```
odooctl migrate rehearse --env production --to 18.0 --keep
```

## Rehearsal flow

1. **Pre-flight check** — if the matrix marks the path `requires_openupgrade: true` and
   `--openupgrade` is not set, the rehearsal fails immediately with a clear message rather
   than running a standard `odoo --update all` that cannot perform a real cross-major upgrade.
2. Clone the source environment DB into a throwaway DB (`<source_db>_mig_rehearsal`).
3. Run the upgrade command against the throwaway DB only.
4. Run the **DB healthcheck** — ping the throwaway DB via `db_adapter.ping(throwaway_db)`.
   After `--stop-after-init`, Odoo is not running, so an HTTP check against the source
   environment's public URL would target the wrong service; only a DB-level ping validates
   the upgraded schema is accessible.
5. Compare module states.
6. Write a JSON report to `<state_dir>/migration_reports/`.
7. Drop the throwaway DB (unless `--keep`).

The throwaway DB name always differs from the source DB name (enforced at
runtime).  Even if the rehearsal fails, the report and cleanup status are
preserved.

## Report

The JSON report at `<state_dir>/migration_reports/` contains:

| Field | Description |
|---|---|
| `status` | `"success"` or `"failed"` |
| `source_env` | Source environment name |
| `source_version` | Odoo version before upgrade |
| `target_version` | Odoo version after upgrade |
| `installed_modules` | Modules present in the upgraded DB |
| `failed_modules` | Modules that failed to upgrade |
| `warnings` | Warnings from scan and upgrade |
| `duration_seconds` | Total rehearsal duration |
| `healthcheck_status` | `"passed"`, `"failed"`, or `"skipped"` |
| `log_path` | Path to the report JSON file |
| `cleanup_status` | `"cleaned"`, `"kept"`, or `"cleanup_failed"` |
| `next_actions` | Recommended next steps |
| `message` | Error message if failed |

## OpenUpgrade (required for all listed paths)

[OpenUpgrade](https://github.com/OCA/OpenUpgrade) is the OCA community upgrade
framework.  All paths in the migration matrix (`paths.yaml`) are marked
`requires_openupgrade: true` — a standard `odoo --update all --stop-after-init` run
against a throwaway clone does **not** perform a real cross-major upgrade and would
produce a misleading success report.

**If `--openupgrade` is not passed for any listed path, the rehearsal fails immediately**
with a clear message and a corrective `next_actions` entry pointing at the flag.

When `--openupgrade` is passed, the pinned branch for the target version is used.
The pinned branches are defined in `odooctl/migration/openupgrade.py`:

```python
PINNED_BRANCHES: dict[str, str] = {
    "16.0": "16.0",
    "17.0": "17.0",
    "18.0": "18.0",
    "19.0": "19.0",
    ...
}
```

Never reference a floating `main` or `master` branch.  Update `PINNED_BRANCHES`
when a new Odoo release gains OpenUpgrade support.

## Safety invariants

- The throwaway DB name is enforced to differ from the source DB name at runtime.
- `dump()` is a read-only `pg_dump` on the source database — it never modifies it.
- `restore()` targets the throwaway DB only.
- The throwaway DB is always dropped in the `finally` block (unless `--keep`).
- A JSON report is always saved — even when the rehearsal fails.
- The production filestore is never read or written by the rehearsal.
- `healthcheck_fn` receives the **throwaway DB name**, not the source environment's public
  URL.  This ensures the healthcheck validates the upgraded throwaway DB, not the live
  source service.
- A path marked `requires_openupgrade: true` in the matrix **always** fails the rehearsal
  unless `--openupgrade` is passed.  The standard `odoo --update all` command cannot
  perform a cross-major upgrade and must not be allowed to produce a misleading success.

## API / runner integration

The `migrate_rehearsal` operation kind is registered in the API and runner:

```
POST /projects/{project}/operations
{
  "kind": "migrate_rehearsal",
  "environment": "production",
  "params": {"to": "18.0", "openupgrade": false}
}
```

Requires `Action.RESTORE` RBAC (admin+ on protected environments).

## Scope

v1 scope is single-host Docker Compose only.  Multi-host or Kubernetes upgrade
automation is out of scope.
