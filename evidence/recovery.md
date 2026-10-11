# P-017 failure recovery

Promise Ledger distinguishes missing evidence from contradictory evidence. A provider failure cannot become a contract violation by accident.

For `P-017`, the primary cloud snapshot probe deliberately returns `AccessDenied`:

```text
P-017-cloud-snapshots
outcome: error
detail: PermissionError: AccessDenied
```

The probe declares a fixed Terraform fallback. The runner executes it only because the primary outcome is `error`:

```text
P-017-terraform-fallback
outcome: pass
detail: configured retention is 30 days; contract maximum is 30
```

The deterministic verdict engine uses the effective fallback result and returns `holds`. If the fallback were absent, the result would be `at_risk`; if the fallback failed, the result would be `violated`.

The complete primary and fallback records, including evidence hashes and trace ID `7e2c834ae151d4de37f08bf4af854495`, are stored in `evidence/run_live_audit.json`. Both executions are instrumented as Neatlogs probe spans.
