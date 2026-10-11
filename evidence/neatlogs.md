# Neatlogs evidence

Promise Ledger uses Neatlogs in the running product, not only during development. The saved audit and compiler benchmark below were executed with the hackathon project key, flushed, and shut down cleanly.

## Trace index

| Workflow | Trace ID | Saved evidence |
| --- | --- | --- |
| Three-document live audit | `7e2c834ae151d4de37f08bf4af854495` | `evidence/run_live_audit.json` |
| Compiler v1 vs. v2 benchmark | `2940581bcb8fa85fec385f6f9a823f0b` | `evidence/benchmark.json` |

Every one of the 16 primary or fallback probe results in the live audit stores the same audit trace ID. The benchmark result stores its own trace ID at the top level. These identifiers are captured from the active Neatlogs/OpenTelemetry context while the workflows are running.

## Runtime coverage

The source instruments the execution boundaries judges need to inspect:

- `ledger_run` and `compiler_benchmark` as `WORKFLOW` spans.
- `promise_extractor`, `check_compiler`, and both compiler semantics as `AGENT` spans.
- `system_inventory` and `probe_runner` as `TOOL` spans.
- `verdict_engine` and `promise_conflict_detector` as `GUARDRAIL` spans.

The P-017 recovery path is preserved in `evidence/run_live_audit.json`: the cloud probe records `AccessDenied` as `error`, the Terraform fallback records `pass`, and the promise verdict is `holds`. Both results carry the live audit trace ID.

## Improvement benchmark

The benchmark replays nine live promises plus one unsupported seeded case.

| Metric | v1 free-form semantics | v2 grounded semantics |
| --- | ---: | ---: |
| Cases | 10 | 10 |
| Verdict mismatches | 3 | 0 |
| False violations | 1 | 0 |
| False holds | 2 | 0 |
| Explicitly unverifiable | 0 | 2 |

The v1 failures are inspectable: it ignores the passing fallback for P-017 and treats missing evidence for P-031 and P-050 as success. The grounded compiler eliminates all three errors while preserving `unverifiable` as an explicit outcome.

## Verification boundary

Local capture, 32-character trace IDs, deterministic result linkage, SDK flush, and shutdown are verified. Signed-in dashboard read-back was also verified on October 11, 2026: the live-audit trace finalized with 36 spans and inspectable input/output, while the benchmark trace finalized with its saved comparison output. A dashboard capture should be included in the demo video; no public sharing link has been created.
