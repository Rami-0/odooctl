# Security Notes

- Do not commit passwords, API tokens, SMTP credentials, payment credentials, OAuth secrets, webhook secrets, S3 keys, or Odoo admin passwords.
- Use environment variables and `*_env` references.
- Logs redact sensitive environment values.
- Protect local backup directories with host filesystem permissions.
- Never clone production into staging without sanitization unless you fully understand the risk.
