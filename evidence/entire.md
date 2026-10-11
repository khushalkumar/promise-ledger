# Entire evidence

Promise Ledger uses Entire Graph during system inventory and keeps the repository configured for Entire checkpoint capture.

## Runtime inventory

`ledger.entire_graph.search_entire_graph` runs this deterministic, read-only shape during `ledger run` and `ledger audit`:

```text
entire graph search --repo <target> --profile full --format json --top-k 10 --query <promise terms>
```

The wrapper has a ten-second timeout and fails closed to an empty hit list when the CLI is missing, times out, returns invalid JSON, or rejects the request. The normal filesystem, database, and Terraform inventory remains available as a fallback.

The traced runtime result is saved in `evidence/run_entire_graph.json` under Neatlogs trace `83d0432252b21bf3a37b25f8f2d1540b`. Its embedded inventory contains ranked Entire Graph evidence, including:

| Rank | Source | Symbol | Lines |
| ---: | --- | --- | ---: |
| 6 | `tasklane/db.py` | `initialize_database` | 12-52 |
| 7 | `tasklane/db.py` | `seed_demo_data` | 55-109 |
| 10 | `tasklane/jobs/purge_tenant.py` | `purge_expired_tenants` | 13-40 |

The purge hit identifies the exact function containing the deliberately omitted `audit_events` table. This evidence is produced by Entire Graph v0.4.0 with the `full` semantic profile, not copied from a hard-coded file list.

## Repository context

- Entire CLI version: 0.11.4.
- `.entire/settings.json` enables checkpoint storage through Git refs.
- Both `promise-ledger` and `tasklane-demo` contain committed Entire configuration.
- The current repo is auto-detected as `gh/khushalkumar/promise-ledger`.

## Checkpoint boundary

The read-only checks currently return no captured checkpoints or sessions, and `entire status` reports that seven Codex hooks need user approval. Hook approval is intentionally not bypassed. Before submission, approve the hooks, capture one final implementation checkpoint, and export `entire checkpoint list --json` plus `entire checkpoint explain <id>` here. Until that happens, this file claims verified Entire Graph runtime use and committed configuration, not checkpoint provenance.
