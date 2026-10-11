# Neatlogs evidence

Promise Ledger uses Neatlogs in the running product, not only during development. The saved audit and compiler benchmark below were executed with the hackathon project key, flushed, and shut down cleanly.

## Trace index

| Workflow | Trace ID | Saved evidence |
| --- | --- | --- |
| Three-document live audit | `279e6c54faac9ee0a38d05177481c551` | `evidence/run_live_audit.json` |
| Autonomous baseline and remediation | `4d46516025921419bc91938c5e90db62` | `evidence/run_autonomous.json` |
| Autonomous selective re-check | `b63c3e0633bc2edc70c08a8d5a4e378c` | `evidence/run_autonomous.json` |
| Independent v1 vs. v2 benchmark | `861bcfead02ad6de99ff5b7a0009bf5f` | `evidence/benchmark-live.json` |

Every one of the 17 primary or fallback probe results in the live audit stores the same audit trace ID. The benchmark result stores its own trace ID at the top level. These identifiers are captured from the active Neatlogs/OpenTelemetry context while the workflows are running.

## Runtime coverage

The source instruments the execution boundaries judges need to inspect:

- `ledger_run` and `compiler_benchmark` as `WORKFLOW` spans.
- `promise_extractor`, `check_compiler_v2`, `compiler_v1_freeform`, investigator, and remediation boundaries as `AGENT` spans.
- `system_inventory` and `probe_runner` as `TOOL` spans.
- `verdict_engine` and `promise_conflict_detector` as `GUARDRAIL` spans.

The P-017 recovery path is preserved in `evidence/run_live_audit.json`: the cloud probe records `AccessDenied` as `error`, the Terraform fallback records `pass`, and the promise verdict is `holds`. Both results carry the live audit trace ID.

## Improvement benchmark

The benchmark makes independent live compiler calls over nine promises plus one unsupported case. V1 generates a probe plan from supported signatures; v2 selects grounded deterministic candidates. Both plans execute through the same runner and verdict engine.

| Metric | v1 free-form semantics | v2 grounded semantics |
| --- | ---: | ---: |
| Cases | 10 | 10 |
| Verdict mismatches | 8 | 0 |
| False violations | 4 | 0 |
| False holds | 0 | 0 |
| Explicitly unverifiable | 0 | 2 |
| Total tokens | 20,381 | 6,608 |
| Estimated model cost | $0.082753 | $0.026435 |
| Wall-clock latency | 38.63 s | 25.70 s |

Free-form v1 missed eight cases: four false violations and four `at_risk` results with a different seeded expectation. Grounded v2 got 10/10, used 67.6% fewer tokens, cost an estimated 68.1% less, and finished 12.93 seconds faster despite one compiler-repair call.

## Verification boundary

Local capture, 32-character trace IDs, deterministic result linkage, SDK flush, and shutdown are verified. Signed-in dashboard read-back was verified for the earlier live audit. The latest autonomous and benchmark trace IDs were captured from active Neatlogs context and stored in their evidence artifacts; confirm their rendered dashboard spans during the final rehearsal. No public sharing link has been created.
