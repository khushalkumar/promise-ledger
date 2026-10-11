# Final audit evidence

## Run

The live audit processed three fictional agreements with three model calls, canonicalized nine promises, executed 16 primary or fallback probe results, and detected one cross-document conflict.

| Signal | Result |
| --- | --- |
| P-014 deletion within 30 days | `violated` - purge coverage, expired rows, and backup retention fail |
| P-017 snapshot retention | `holds` - cloud `AccessDenied` recovers through passing Terraform evidence |
| P-021 EU data residency | `violated` - `us-east-1` is outside the promised boundary |
| P-031 subprocessor notice | `unverifiable` - no authoritative evidence source exists |
| P-040 through P-044 | `holds` |
| C-003 retention conflict | `violated` - DPA says 30 days while the policy allows 90 |

The saved result is `evidence/run_live_audit.json`. All 16 probe results link to dashboard-verified Neatlogs trace `7e2c834ae151d4de37f08bf4af854495`.

## Remediation

Two independent private Tasklane PRs fix the two P-014 root causes:

- [PR #1: include audit events in tenant deletion](https://github.com/khushalkumar/tasklane-demo/pull/1)
- [PR #2: cap backup retention at 30 days](https://github.com/khushalkumar/tasklane-demo/pull/2)

The PR heads were combined in an isolated checkout. The Tasklane test suite passed and the re-check turned P-014 to `holds`; the saved result is `evidence/run_remediated.json`. Neither PR is merged, so the baseline demo remains reproducible.

## Improvement and economics

- The ten-case compiler benchmark moves from three v1 mismatches to zero v2 mismatches and is linked to Neatlogs trace `2940581bcb8fa85fec385f6f9a823f0b`.
- The latest verified live run used 2,886 prompt and 920 completion tokens, or $0.016415 at the stated scenario prices. The cfo.ai model conservatively retains the earlier 929-completion-token measurement and $0.016505 cost assumption.
- The four-page business plan is in `docs/business_plan.pdf` and the cfo.ai entry rows are in `evidence/cfo_inputs.csv`.

## Remaining submission captures

- Include the verified signed-in Neatlogs trace in the final demo capture.
- Show Entire checkpoint `01M4MZGFHEEK939T4JXBCBWNZH`; its list and explanation exports are committed under `evidence/`.
- Replace build-in-public draft slots with published links only after explicit posting approval.

The cfo.ai model is complete. Its three scenarios were verified against the prepared inputs, and the exported workbook plus rendered comparison are recorded in `evidence/cfo.md`.
