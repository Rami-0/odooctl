# Domains and SSL

odooctl manages domain routing and TLS through an explicit reverse proxy abstraction. V1 supports **Traefik only**; nginx/Caddy are future adapters.

## Architecture

```
odooctl domain attach/verify/detach
    └── DomainService
            └── ReverseProxyAdapter (Protocol)
                    └── TraefikAdapter (v1 only)
```

The `DomainService` calls the adapter interface — never Traefik directly. Switching to another proxy in future requires only a new adapter that implements `ReverseProxyAdapter`.

## Commands

### Attach a domain

```sh
odooctl domain attach production odoo.example.com
```

Writes a Traefik dynamic config fragment at `.odooctl/traefik-dynamic/odooctl-production.yml`. Traefik hot-reloads the file; the global proxy is never restarted.

### Detach a domain

```sh
odooctl domain detach production odoo.example.com
```

Removes the dynamic config file. The route disappears on Traefik's next poll cycle.

### Verify domain status

```sh
odooctl domain verify production
odooctl domain verify production --expected-ip 1.2.3.4
```

Reports three dimensions:

| Dimension | Values | Meaning |
|-----------|--------|---------|
| DNS | `ok` / `mismatch` / `failed` / `unknown` | Whether the domain resolves to the expected host IP |
| Cert | `active` / `unknown` / `none` | TLS certificate status inferred from route config |
| Proxy | `active` / `inactive` | Whether the Traefik route file exists |

If `--expected-ip` is omitted, DNS status is `unknown` with a note rather than failing. This is safe when the host IP is not pre-configured.

## Traefik integration

odooctl writes standard Traefik v2 dynamic config under the configured dynamic directory (`.odooctl/traefik-dynamic/` by default). For HTTPS routes, `tls.certResolver: acme` is set so Traefik handles ACME/Let's Encrypt automatically. For wildcard/DNS-01 certificates, configure Traefik's DNS challenge resolver separately; odooctl only writes the router declaration.

Example generated file (`.odooctl/traefik-dynamic/odooctl-production.yml`):

```yaml
http:
  routers:
    odooctl-production:
      entryPoints:
        - websecure
      rule: Host(`odoo.example.com`)
      service: odooctl-production
      tls:
        certResolver: acme
  services:
    odooctl-production:
      loadBalancer:
        servers:
          - url: http://localhost:8069
```

## Safety rules

- **Never restarts the global proxy** — Traefik hot-reloads file changes.
- **Idempotent attach** — re-attaching overwrites the route file safely.
- **Idempotent detach** — detaching a non-existent route is a no-op.
- **DNS verification is optional** — if `--expected-ip` is not provided, the verify command reports `unknown` DNS status rather than failing.
