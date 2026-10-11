# Promise Ledger three-minute demo

## Before recording

1. Keep both repositories private until the submission switch.
2. Seed `tasklane-demo/artifacts/tasklane.db` from Tasklane `main`.
3. Run the live audit and leave the ledger UI open at the top of the page.
4. Open Tasklane PR #1, Tasklane PR #2, `evidence/run_remediated.json`, Neatlogs trace `279e6c54faac9ee0a38d05177481c551`, and benchmark trace `2940581bcb8fa85fec385f6f9a823f0b` in separate tabs.
5. Confirm no secrets, private browser chrome, or unrelated tabs are visible.
6. Keep both remediation PRs unmerged; the isolated combined re-check is the proof artifact.

## 0:00-0:20 - The promise

**Screen:** Contract PDF beside the ledger hero.

**Say:**

> Contracts promise outcomes, but evidence lives across code, data, cloud configuration, and policies. Promise Ledger turns each clause into a chain of proof. This run reads three real documents and checks nine promises against a fictional SaaS called Tasklane.

## 0:20-1:05 - The live ledger

**Screen:** Start at the hero, then scroll to `P-014`.

**Say:**

> The audit found three red signals: two system violations and one document conflict. `P-014` requires customer data and backups to be deleted within 30 days. The static probe finds that the purge job omits `audit_events`; the data probe finds 1,284 expired rows; and Terraform shows 90-day backup expiry. Every result points back to the exact DPA clause.

Pause briefly on `P-021` and `P-031`.

> Residency is also violated because exports use `us-east-1`. The subprocessor promise is different: there is no authoritative evidence source, so the result is `unverifiable`, not a fabricated pass or failure.

## 1:05-1:35 - Recovery, not false confidence

**Screen:** Open `P-017` and its Neatlogs trace.

**Say:**

> The cloud snapshot check returns `AccessDenied`. Promise Ledger records an error and executes the probe's declared Terraform fallback. Terraform proves 30-day retention, so the final verdict is `holds`. Infrastructure failure never silently becomes a contract violation.

## 1:35-2:10 - Fix and prove

**Screen:** Tasklane PR #1, then PR #2, then the remediated evidence artifact.

**Say:**

> The two root causes become two small reviewable PRs. The first adds `audit_events` to the purge transaction. The second changes backup expiry from 90 days to 30, without touching the separate residency defect. Applying both PRs in an isolated checkout and running the purge turns `P-014` green. Residency and the policy conflict stay red, so the re-check proves the intended fix instead of hiding other problems.

## 2:10-2:35 - A reliable agent

**Screen:** Show the v1-v2 benchmark, then the Entire Graph hit for `purge_expired_tenants`.

**Say:**

> A naive compiler mislabels three of ten seeded cases: it treats missing evidence as success and an access error as a violation. The grounded compiler makes zero of those mistakes. Neatlogs preserves both benchmark semantics as separate spans, and Entire Graph locates the exact purge function from the contract terms during runtime inventory.

## 2:35-3:00 - The business

**Screen:** The cfo.ai scenario model, then `docs/business_plan.pdf`.

**Say:**

> The live audit used about 3.8 thousand tokens across three calls, about 1.7 cents at the conservative model-price assumption in the plan. Token cost is not the margin constraint; review support and infrastructure are. The base model prices monitored contracts at $39 per month and reaches roughly 76% gross margin. Promise Ledger makes contract truth testable, fixable, and economically practical.

End on the ledger hero and the line: **Every promise gets a chain of proof.**
