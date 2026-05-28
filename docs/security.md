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
