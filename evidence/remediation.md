# P-014 remediation proof

Promise Ledger found two independent root causes for the Northwind DPA section 7.2 deletion promise. Each fix is isolated in an open Tasklane pull request so the planted baseline remains reproducible on `main`.

## Pull requests

1. [Tasklane PR #1](https://github.com/khushalkumar/tasklane-demo/pull/1) - commit `11aa2452f92db94fbf4d0edeec4aaea2fa1fdaeb` adds `audit_events` to the tenant purge transaction and converts the planted defect assertion into a regression test.
2. [Tasklane PR #2](https://github.com/khushalkumar/tasklane-demo/pull/2) - commit `13470446b2582a4a2a4396d16e850e62d253e60b` reduces backup lifecycle expiry from 90 days to 30 days while leaving the separate residency defect untouched.

Both commits are authored by Khushal Kumar using `kkhushal1531@gmail.com`.

## Combined verification

The two PR commits were applied to an isolated checkout based on Tasklane `main`. The verification sequence was:

```text
uv run pytest -q
uv run tasklane-seed artifacts/tasklane.db
purge_expired_tenants(... retention_days=30)
ledger run ... --output evidence/run_remediated.json
```

All six Tasklane tests passed. After the purge job ran, Promise Ledger changed `P-014` from `violated` to `holds` across static coverage, expired tenant rows, and backup lifecycle configuration.

The re-check deliberately preserves the remaining conditions:

- `P-021` remains `violated` because the exports provider is still in `us-east-1`.
- `P-031` remains `unverifiable` because no authoritative subprocessor source exists.
- `C-003` remains `violated` because the public policy still allows 90 days while the DPA requires 30 days.

The complete machine-readable result is `evidence/run_remediated.json`. Neither pull request was merged during this verification.
