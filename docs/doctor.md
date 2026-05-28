# Doctor

`odooctl doctor` runs safe preflight checks for an Odoo project without mutating the stack.

```bash
odooctl doctor
odooctl -p acme doctor
odooctl -C /srv/odoo/acme doctor --json
```

Checks include:

- config file can be loaded
- project root exists
- Compose file exists
- referenced environment variables are set
- referenced sanitization SQL files exist
- weak/common secret warning for values shorter than `redaction.min_secret_length` or listed in `redaction.ignore_values`

JSON mode returns a list of check objects:

```json
[
  {"name": "config", "ok": true, "message": "config loaded: /srv/odoo/acme/odooctl.yml"},
  {"name": "environment", "ok": true, "message": "all referenced environment variables are set"}
]
```

Use `doctor` before installing schedules, running production backups, or cloning production into staging.
