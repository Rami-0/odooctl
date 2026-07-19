# Integration test status

Latest run of the real-Odoo integration matrix (`tests/integration/`).

| Date       | Odoo versions       | Result           | Notes |
| ---------- | ------------------- | ---------------- | ----- |
| 2026-07-19 | 17.0, 18.0, 19.0    | 21 passed (7/version) | Full lifecycle green on all three majors: validate, doctor, status, backup --verify, clone with SQL-asserted sanitization, restore --to, API-enqueue → runner --once parity, foreign-container isolation. ~4 min total on a 4-core host. |

Reproduce:

```bash
ODOOCTL_IT_VERSIONS=17.0,18.0,19.0 pytest -m integration tests/integration
```

See `docs/operations/integration-testing.md` for what the harness covers and
its isolation guarantees.
