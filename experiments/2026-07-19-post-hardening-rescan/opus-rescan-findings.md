# Post-hardening adversarial re-scan — Opus (2026-07-19)

Read-only re-scan of the tree after the Phase 1–2 hardening. All 13 prior
remediations verified SOLID except audit-chain (H2) and nonce store (H3) which
were found weaker than the rest of the codebase. Token forgery/alg-confusion
not exploitable; secret-store crypto correct; identifier/hostname validators
defeat unicode/control-char/leading-dash/overlength attacks.

## Resolution status (2026-07-19)

All findings addressed. H1/H2/H3/M1/M2/M4/L1 fixed with tests (976 unit tests
green on pinned + latest deps, ruff clean). M3 accepted as low-risk (data is
recoverable via the temp DB under verify-before-destroy; the adapter protocol
exposes no DB-existence query to implement a rename-aside swap cleanly). L2
mitigated by existing doctor warnings + documented secret-strength guidance.

## New / incomplete findings (acted on)

- **H1 HIGH (incomplete)** — token `proj` claim enforced only on `/operations/{id}`,
  `/events`, `/cancel`; NOT on `POST /projects/{project}/operations` (enqueue) nor
  any `routes_projects.py` read route. A per-project token can read/enqueue against
  another project. Fix: shared dependency comparing `token_project` to path `{project}`.
- **H2 MED/HIGH (incomplete)** — audit chain doesn't detect tail-truncation or
  whole-file deletion (empty → verify True); runner builds `AuditStore` with no key,
  so default deployment is unkeyed. Fix: seq numbers + MAC'd high-water mark; runner
  passes key + warns when unkeyed.
- **H3 MED (incomplete)** — `NonceStore.mark_consumed` is lock-free, non-atomic
  truncate-write; crash → empty JSON → all nonces forgotten → replay. TTL>7200s purged
  before expiry. Fix: flock + tmp+os.replace; bound TTL to retention.
- **M1 MED (new)** — no check that one env's `db_name` equals another's
  `db_name + temp_db_suffix`; a clone/restore can DROP a different env's live DB. Fix:
  reject in `validate_environment_graph`.
- **M2 LOW/MED (new)** — `filestore_path` unvalidated; `/` basename empties → could
  wipe filestore root; host adapter rmtree on arbitrary path. Fix: validate absolute,
  non-empty basename, no `..`.
- **M4 LOW/MED (incomplete)** — weak-key floor conditional on env-var provenance in
  `get_principal`/`create_app`. Fix: unconditional `enforce_key_strength(api_key)`.
- **M3 LOW (new)** — DB swap DROP-then-RENAME not truly atomic (verify-before-destroy
  preserved; data recoverable). Deferred: acceptable, documented.
- **L1 LOW (new)** — `"testclient"` in default `allowed_hosts`. Fix: gate behind test.
- **L2 LOW (incomplete)** — secrets <6 chars / common words bypass shell redactor.
  Mitigation: doctor already warns; secret-strength guidance in docs.
