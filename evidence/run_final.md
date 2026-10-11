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

The saved result is `evidence/run_live_audit.json`. All 17 probe results link to Neatlogs trace `53200c3288d182341125ec2408af6135`.

## Remediation

Two independent private Tasklane PRs fix the two P-014 root causes:

- [PR #1: include audit events in tenant deletion](https://github.com/khushalkumar/tasklane-demo/pull/1)
- [PR #2: cap backup retention at 30 days](https://github.com/khushalkumar/tasklane-demo/pull/2)

The PR heads were combined in an isolated checkout. The Tasklane test suite passed and the re-check turned P-014 to `holds`; the saved result is `evidence/run_remediated.json`. Neither PR is merged, so the baseline demo remains reproducible.

## Improvement and economics

- The ten-case compiler benchmark moves from three v1 mismatches to zero v2 mismatches and is linked to Neatlogs trace `2940581bcb8fa85fec385f6f9a823f0b`.
- The measured live run used 2,886 prompt and 929 completion tokens. At the stated scenario prices, that is $0.016505 per audit.
- The four-page business plan is in `docs/business_plan.pdf` and the cfo.ai entry rows are in `evidence/cfo_inputs.csv`.

## Remaining submission captures

- Add signed-in Neatlogs screenshots or public trace links.
- Add the cfo.ai model screenshot/export after entering the prepared rows.
- Add final Entire checkpoint evidence after the Codex hooks are approved.
- Replace build-in-public draft slots with published links only after explicit posting approval.
