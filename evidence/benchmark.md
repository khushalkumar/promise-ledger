# Compiler benchmark

The benchmark executes the nine-promise audit plus one unsupported promise with known expected verdicts. It was run live on October 11, 2026; it does not replay saved predictions.

`v1` independently generates templates, parameters, dependencies, and fallbacks from the promise, inventory, and supported template signatures. `v2` independently selects deterministically generated asset-grounded candidates. Both plans run through the same bounded probe runner and verdict engine.

| Metric | v1 | v2 |
| --- | ---: | ---: |
| Seeded cases | 10 | 10 |
| Verdict mismatches | 8 | 0 |
| False violations | 4 | 0 |
| False holds | 0 | 0 |
| Unverifiable verdicts | 0 | 2 |
| LLM calls | 10 | 11 |
| Prompt tokens | 16,141 | 5,286 |
| Completion tokens | 4,240 | 1,322 |
| Total tokens | 20,381 | 6,608 |
| Wall-clock latency | 38.63 s | 25.70 s |
| Estimated model cost | $0.082753 | $0.026435 |

V1 correctly found `P-014` and `P-043`, but produced four false violations and four `at_risk` results where the seeded expected verdict was different. It mis-handled the `P-017` fallback and failed to preserve explicit `unverifiable` behavior for `P-031` and `P-050`. V2 classified all ten cases correctly.

The grounded v2 path used 13,773 fewer tokens (67.6%), cost an estimated 68.1% less, and completed 12.93 seconds faster. It used one repair call for an incomplete selection. Executable behavior remained constrained to audited templates, fallback semantics were deterministic, and missing authority became `unverifiable`.

The measured output is stored in `evidence/benchmark-live.json`. Neatlogs trace `861bcfead02ad6de99ff5b7a0009bf5f` contains the benchmark workflow and separate v1/v2 spans. Cost uses the configured benchmark assumptions of $2.50 per million input tokens and $10.00 per million output tokens; it is an estimate, not a provider invoice.
