# Staging Clone

`odooctl clone production staging --sanitize` dumps production, restores into staging, copies filestore, applies built-in and project SQL sanitizers, updates configured modules, restarts Odoo, and checks `/web/login`.

Sanitization is enabled by default because staging must not send real emails, call live payment APIs, or trigger production webhooks.
