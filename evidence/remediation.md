# P-014 remediation proof

Promise Ledger found two independent root causes for the Northwind DPA section 7.2 deletion promise. Each fix is isolated in an open Tasklane pull request so the planted baseline remains reproducible on `main`.

## Pull requests

1. [Tasklane PR #3](https://github.com/khushalkumar/tasklane-demo/pull/3) - runtime-created commit `5a153a843f1c5daadaa187f66212fbf081089d94` adds `audit_events` to the tenant purge transaction. Entire checkpoint: `01M4NGGEP8TWQWXQ5VXDV28D7V`.
2. [Tasklane PR #4](https://github.com/khushalkumar/tasklane-demo/pull/4) - runtime-created commit `7a98105b3d669ae5bc0c574a2ae6539298c17dc6` reduces backup lifecycle expiry from 90 days to 30 days while leaving the separate residency defect untouched. Entire checkpoint: `01M4NGP8171K9MSW1N78X8PB19`.

Both are normal, non-draft PRs created by autonomous run `pl-20261011T130117Z-6f374997`. Both commits are authored by Khushal Kumar using `kkhushal1531@gmail.com`; both GitHub Actions checks pass.

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
