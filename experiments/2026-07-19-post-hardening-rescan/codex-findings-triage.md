# Codex (GPT) re-scan triage — 2026-07-19

Second cross-model adversarial review (GPT via codex CLI, read-only) after the
Opus fixes. It confirmed the shell-injection, protected-env, password-on-argv,
nonce-bounding, project-scoping, and key-length remediations hold, and raised
7 findings. Full output: `codex-review.md`.

## Fixed (with tests)

- **#3 HIGH — DB swap not atomic.** (Also Opus M3, which had been accepted as
  low-risk; codex rating it HIGH tipped the decision.) `swap_temp_database`
  now, when the adapter exposes `database_exists`, renames the live target
  aside, promotes the temp DB, and restores the original if the promotion
  rename fails — the target name is never left absent. Real adapters gained
  `database_exists`; fakes keep the documented drop-then-rename fallback.
- **#6 MED — registry config-path containment bypassed by API/runner.** Added
  `registry.context_from_registered()` (enforces `_contained_config_path`) and
  routed the API loaders (`routes_projects._load_ctx`,
  `routes_operations._load_ctx`/`_find_op_ctx`) and the runner through it, so a
  hand-edited `config="../../evil.yml"` is rejected everywhere, not just in the
  CLI.
- **#4 MED — CommandError redacted against os.environ, not the call env.**
  `CommandError` now redacts its composed message with the merged per-call
  environment, so a secret passed only via `env=` (e.g. `PGPASSWORD`) is
  redacted from argv/stderr echoes. (`result.args` intentionally retains the
  raw argv for programmatic inspection — documented; the string form is safe.)
- **#1 HIGH — unvalidated filestore tar extraction.** Host `restore_archive`
  now validates every archive member before extraction (rejects absolute
  paths, `..` traversal, symlink/hardlink, and device/fifo members) and passes
  `--no-same-owner --no-same-permissions`. Extraction still stages into a
  private temp dir before the atomic move.

## Accepted / deferred with rationale

These hold only under, or are bounded by, the documented **operator-trust
model** (`docs/security.md`: anyone who can write `odooctl.yml` or the state
directory is an operator).

- **#2 HIGH — restore/clone replace the filestore before DB promotion.** Real:
  a failure after the filestore is replaced but before the DB swap leaves
  filestore and DB inconsistent. Mitigated in part by #3 (the DB swap itself no
  longer loses the target). Full filestore-staging-with-rollback is a larger
  change tracked for a follow-up before 1.0 GA; until then the pre-deploy
  backup is the recovery path and restore/clone target non-production by policy.
- **#5 MED — audit chain unkeyed by default is forgeable.** By design the chain
  and its high-water mark are plain SHA-256 unless `ODOOCTL_AUDIT_KEY` is set;
  an operator with state-dir write access (already trusted) can rewrite both.
  The runner warns when unkeyed. Making the key mandatory (fail-closed) is a
  deployment-policy option documented for hardened installs, not a v1 default
  (it would break every existing unkeyed deployment).
- **#7 MED — capability tokens don't bind op_id/params.** A party who can
  rewrite a queued entry before nonce consumption (state-dir write access,
  operator-trusted) could alter params within the token's action/env/project
  scope. Binding a params digest + op_id into signed claims is a worthwhile
  hardening tracked for a follow-up; it does not cross the trust boundary as
  it stands.
