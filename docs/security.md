# Security Notes

- Do not commit passwords, API tokens, SMTP credentials, payment credentials, OAuth secrets, webhook secrets, S3 keys, or Odoo admin passwords.
- Use environment variables and `*_env` references.
- Logs redact sensitive environment values whose variable names look secret-bearing (`PASSWORD`, `SECRET`, `TOKEN`, `KEY`, `PASSWD`).
- Redaction intentionally skips short/common values from `redaction.ignore_values` such as `odoo`; otherwise logs become unreadable in local Odoo stacks. Use strong, unique production secrets.
- Run `odooctl doctor` after exporting env vars. It warns when referenced secrets are shorter than `redaction.min_secret_length` or ignored by the redaction policy.
- Protect local backup directories with host filesystem permissions.
- Install `odooctl[s3]` and configure real S3 credentials for off-host backup copies. If remote upload cannot run, `odooctl` warns and writes a local mirror under `.odooctl/remote-backups/`.
- Never clone production into staging without sanitization unless you fully understand the risk.
- Staging sanitization disables mail servers, fetchmail, crons, payment providers, queue jobs, and pending outbound mail by default.

## Trust model

The audits of 2026-05-31 asked one load-bearing question: *who is trusted to
write `odooctl.yml`?* The answer defines the severity of every config-driven
finding, so it is stated here explicitly.

### `odooctl.yml` is operator-trusted

- Anyone who can write the project config (or the files it references, such as
  the compose file) is considered an **operator** of that project. The config
  is not a security boundary: an actor who controls it already controls what
  `docker compose` runs and can therefore execute arbitrary commands with the
  runner's privileges by design.
- Consequently, protect `odooctl.yml` like you protect the compose file:
  repository write access, host filesystem permissions, and code review are
  the controls. `odooctl` will never mitigate a hostile config author.
- Defense in depth still applies: config values that flow into subprocess
  arguments, container paths, volume names, or reverse-proxy rules are
  validated at load time (charset/length/hostname rules), and no code path
  builds `sh -c` command strings from config values. These measures limit the
  blast radius of *mistakes* (typos, malformed generated configs, copy-paste)
  — they are not a sandbox for malicious operators.

### Boundaries that ARE enforced

- **Web/API tier vs runner**: the API process never mounts the Docker socket
  and never imports privileged modules (enforced by `security/runner_contract`).
  API clients act under RBAC roles; destructive operations require capability
  tokens minted with the runner key, verified with single-use nonces.
- **Roles**: viewers cannot mutate; operators cannot bypass protected-environment
  floors; protected environments (`is_protected()`: the `production` name or
  any env with `tier: production`) require elevated confirmation paths.
- **Secrets**: referenced by env-var name in config, resolved only at execution
  time in the privileged process, redacted from logs, errors, and streamed
  operation events.

If your deployment needs a lower-trust config-authoring role (e.g. developers
may edit addon lists but not volumes or compose paths), put that policy in
your VCS review process — odooctl deliberately does not implement partial
config trust in v1.
