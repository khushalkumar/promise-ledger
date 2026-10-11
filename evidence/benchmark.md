# Compiler benchmark

The benchmark replays the nine-promise live audit plus one seeded unsupported promise with known expected verdicts.

`v1` represents naïve free-form semantics: it checks primary evidence only, treats any probe error as a violation, and assumes a promise holds when no probe exists. `v2` is the current asset-grounded compiler with fixed templates, declared fallbacks, and explicit `unverifiable` semantics.

| Metric | v1 | v2 |
| --- | ---: | ---: |
| Seeded cases | 10 | 10 |
| Verdict mismatches | 3 | 0 |
| False violations | 1 | 0 |
| False holds | 2 | 0 |
| Unverifiable verdicts | 0 | 2 |

The three v1 failures are intentional and inspectable:

- `P-017`: `AccessDenied` becomes a false violation because v1 ignores the passing Terraform fallback.
- `P-031`: the missing subprocessor evidence becomes a false hold because v1 treats zero probes as success.
- `P-050`: a seeded unsupported promise also becomes a false hold instead of `unverifiable`.

The comparison is deterministic and stored in `evidence/benchmark.json`. The benchmark workflow and both compiler semantics are instrumented as separate Neatlogs spans.
