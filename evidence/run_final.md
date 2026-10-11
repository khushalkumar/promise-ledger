# Final audit evidence

## Run

The live audit processed three fictional agreements with three model calls, canonicalized nine promises, executed 17 primary or fallback probe results, and detected one cross-document conflict.

| Signal | Result |
| --- | --- |
| P-014 deletion within 30 days | `violated` - purge coverage, expired rows, and backup retention fail |
| P-017 snapshot retention | `holds` - cloud `AccessDenied` recovers through passing Terraform evidence |
| P-021 EU data residency | `violated` - `us-east-1` is outside the promised boundary |
| P-031 subprocessor notice | `unverifiable` - no authoritative evidence source exists |
| P-040 through P-044 | `holds` |
| C-003 retention conflict | `violated` - DPA says 30 days while the policy allows 90 |

The saved result is `evidence/run_live_audit.json`. All 17 probe results link to dashboard-verified Neatlogs trace `279e6c54faac9ee0a38d05177481c551`.

## Remediation

Autonomous run `pl-20261011T130117Z-6f374997` created two independent private Tasklane PRs for the two P-014 root causes:

- [PR #3: include audit events in tenant deletion](https://github.com/khushalkumar/tasklane-demo/pull/3)
- [PR #4: cap backup retention at 30 days](https://github.com/khushalkumar/tasklane-demo/pull/4)

The PR heads were combined in an isolated checkout. The Tasklane test suite passed and the re-check turned P-014 to `holds`; the saved result is `evidence/run_remediated.json`. Neither PR is merged, so the baseline demo remains reproducible.

## Improvement and economics

- The independent ten-case compiler benchmark produced eight v1 mismatches and zero v2 mismatches. Grounded v2 used 6,608 tokens versus v1's 20,381, cost an estimated $0.026435 versus $0.082753, and completed 12.93 seconds faster. It is linked to Neatlogs trace `861bcfead02ad6de99ff5b7a0009bf5f`.
- The latest verified live run used 2,886 prompt and 938 completion tokens, or $0.016595 at the stated scenario prices. The cfo.ai model retains its earlier 929-completion-token measurement and $0.016505 cost assumption.
- The four-page business plan is in `docs/business_plan.pdf` and the cfo.ai entry rows are in `evidence/cfo_inputs.csv`.

## Remaining submission captures

- Include the verified signed-in Neatlogs trace in the final demo capture.
- Show runtime-created PR checkpoints `01M4NGGEP8TWQWXQ5VXDV28D7V` and `01M4NGP8171K9MSW1N78X8PB19`.
- Replace build-in-public draft slots with published links only after explicit posting approval.

The cfo.ai model is complete. Its three scenarios were verified against the prepared inputs, and the exported workbook plus rendered comparison are recorded in `evidence/cfo.md`.
