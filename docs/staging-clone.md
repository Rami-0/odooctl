# Staging Clone

`odooctl clone production staging --sanitize` dumps production, restores into staging, copies filestore, applies built-in and project SQL sanitizers, updates configured modules, restarts Odoo, and checks the configured health path (default `/web/health`).

Sanitization is enabled by default because staging must not send real emails, call live payment APIs, or trigger production webhooks.

The clone restores into a transient `<db_name>_incoming` database and then
atomically renames it into place. Sessions on the incoming database are severed
immediately before that rename, so the swap succeeds even when `db_selector:
true` and the running Odoo has auto-connected to every visible database
(otherwise the rename would fail with *"database is being accessed by other
users"*). The same guard applies to `odooctl restore`.

## Built-in sanitization coverage

All built-in statements are guarded (`to_regclass` / `information_schema.columns`) so they no-op on Odoo versions where a table or column does not exist.

Every profile (`minimal`, `normal`, `strict`) applies the mandatory baseline:

- Disables outgoing mail servers (`ir_mail_server`) and incoming mail (`fetchmail_server`).
- Disables all crons (`ir_cron`) — including under `minimal`; a cloned production database with live crons can send mail and charge cards.
- Disables payment providers in both the modern `payment_provider` table (Odoo 16+) and the legacy `payment_acquirer` table (pre-16).
- Cancels pending `queue_job` records and disables `base_automation` rules.
- Purges the unsent mail queue (`mail_mail`).
- Scrubs webhook/callback/endpoint URLs and `api_key`/`secret`/`token`/`password` system parameters.
- Rewrites `web.base.url` to the staging domain and sets `web.base.url.freeze = True` (inserting the parameter if missing) so Odoo cannot rewrite the URL back to production on the next admin login.

`normal` (the default) and `strict` additionally scrub credential material carried over from production:

- Disables OAuth providers (`auth_oauth_provider`: `enabled`/`active` set to false) and clears `client_secret` where the column exists.
- Clears IAP/SMS tokens (`iap_account.account_token`).
- Deletes WebAuthn passkeys (`auth_passkey_key`, Odoo 19 `auth_passkey` module) so production passkeys cannot unlock staging; no-ops on older versions.

`strict` also blanks every `auth_%` system parameter.
