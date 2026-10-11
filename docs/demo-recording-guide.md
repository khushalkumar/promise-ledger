# Promise Ledger demo recording guide

This guide assumes you have never seen the project before. You do not need to run code, use a terminal, or understand JSON while recording. The demo is a guided tour of already verified evidence.

## 1. What you are demonstrating

Promise Ledger reads agreements, converts their clauses into named promises, checks those promises against a fictional SaaS called Tasklane, and preserves the evidence for each verdict.

The main example is `P-014`. `P-014` is an internal label, not a priority or ticket number. It represents this clause from the fictional Northwind contract:

> Tasklane will delete Northwind's customer personal data within 30 days, including application records, audit events, exports, attachments, and backups.

The original audit marks `P-014` as **violated**. The proposed fixes make it **hold** in an isolated verification run.

## 2. Where everything is

### Screens used in the recording

| What | Where to open it | What you should see |
| --- | --- | --- |
| Northwind demo contract | [`contracts/Northwind_DPA_v3.pdf`](../contracts/Northwind_DPA_v3.pdf) | A one-page PDF titled **Northwind Data Processing Addendum**. Section 7.2 contains the 30-day deletion promise. |
| Original audit UI | <http://127.0.0.1:8000> | Promise Ledger page. The top says **Every promise gets a chain of proof**. `P-014` is red and says **VIOLATED**. |
| Original Neatlogs trace | [Trace `279e...c551`](https://app.neatlogs.com/traces/279e6c54faac9ee0a38d05177481c551?orgId=5d26aec1-b6b1-4572-b322-3f0ad165c998&projectId=61db443d-602a-484c-9136-1ae03eb5ae03) | The `ledger_run` trace with 37 spans. Use it to show the recorded workflow and the P-017 fallback. |
| Tasklane fix 1 | [Tasklane PR #1](https://github.com/khushalkumar/tasklane-demo/pull/1) | A small code change adding `audit_events` to the deletion job. |
| Tasklane fix 2 | [Tasklane PR #2](https://github.com/khushalkumar/tasklane-demo/pull/2) | A Terraform change reducing backup expiry from 90 days to 30 days. |
| Fixed-result UI | <http://127.0.0.1:8001> | The same Promise Ledger page using the isolated remediated result. `P-014` is green and says **HOLDS**. |
| Benchmark trace | [Trace `2940...3f0b`](https://app.neatlogs.com/traces/2940581bcb8fa85fec385f6f9a823f0b?orgId=5d26aec1-b6b1-4572-b322-3f0ad165c998&projectId=61db443d-602a-484c-9136-1ae03eb5ae03) | The compiler benchmark. The important result is v1: 3 mismatches; v2: 0 mismatches. |
| Benchmark backup | [`evidence/benchmark.md`](../evidence/benchmark.md) | The same benchmark in a simple table if the Neatlogs page is slow. |
| Entire evidence | [`evidence/entire.md`](../evidence/entire.md) | Shows that Entire Graph found `purge_expired_tenants` in `tasklane/jobs/purge_tenant.py`. |
| cfo.ai model | [Promise Ledger scenario page](https://app.cfo.ai/outgoing-sheep-2dce4103/chat/ff58a708-efba-45ab-adce-dcf04fd52383?pageId=e21c5cbf-b709-43da-a9cd-9c7be1769de2&panel=page&scenario=9e525b60-f4d7-4c9f-aef4-6101c66d1453) | The Downside, Base, and Growth financial scenarios. |
| cfo.ai backup image | [`evidence/cfo_scenario_model.png`](../evidence/cfo_scenario_model.png) | A static image of the scenario table if the live cfo.ai page is slow. |
| Business plan | [`docs/business_plan.pdf`](business_plan.pdf) | A four-page PDF titled **Promise Ledger - Business Plan**. |

The two `127.0.0.1` addresses are pages served from this Mac. They are not public websites. I will confirm both are running before recording.

## 3. What the original audit page means

The original audit page at <http://127.0.0.1:8000> is a read-only visual report. There are no buttons to press. You only scroll.

At the top:

- **Red signals: 3** means two violated system promises plus one conflict between documents.
- **Promises: 9** means nine contractual obligations were extracted.
- **Source documents: 3** means two generated contracts and one policy were checked.
- **Unverifiable: 1** means one promise did not have an authoritative evidence source. The system refuses to invent a pass or failure.

Important cards:

- `P-014` — deletion within 30 days. Red because deletion code, old database rows, and backup retention disagree with the promise.
- `P-017` — database snapshot retention. Green because a failed cloud check safely falls back to Terraform evidence.
- `P-021` — EU data residency. Red because the system is configured for `us-east-1`, not the promised `eu-west-1`.
- `P-031` — subprocessor notice. Unverifiable because no authoritative source exists.

## 4. Before recording

### Prepare the browser

Open the items from section 2 in this order:

1. Northwind contract PDF.
2. Original audit UI (`8000`).
3. Original Neatlogs trace.
4. Tasklane PR #1.
5. Tasklane PR #2.
6. Fixed-result UI (`8001`).
7. Benchmark trace or benchmark Markdown backup.
8. Entire evidence.
9. cfo.ai scenario model or its backup image.
10. Business-plan PDF.

Close unrelated tabs and hide bookmarks, notifications, email, Slack, and anything containing credentials. Keep the GitHub PRs unmerged.

### Start macOS screen recording

1. Press `Shift-Command-5`.
2. Select **Record Entire Screen**.
3. Click **Options**.
4. Under **Microphone**, select the microphone you will speak into.
5. Under **Save to**, select Desktop or another folder you can find easily.
6. Turn off **Show Mouse Clicks** unless you want the click circles visible.
7. Click **Record**.
8. Wait two seconds before speaking.

Use normal browser zoom, usually 100%. Move the pointer away from text after switching tabs.

## 5. The six scenes, click by click

### Scene 1 — The contractual promise — 0:00 to 0:20

**Open:** the Northwind contract PDF.

**Place on screen:** the whole one-page PDF. Section **7.2 Deletion and backup retention** should be readable. If necessary, zoom until section 7.2 is visible.

**Action:** pause on section 7.2 for about five seconds, then switch to the original audit UI at `http://127.0.0.1:8000` and remain at the top.

**Say:**

> Contracts promise outcomes, but the evidence lives across code, data, infrastructure, and policies. Promise Ledger turns each clause into a chain of proof. This fictional DPA requires Tasklane to delete customer data and backups within 30 days.

### Scene 2 — The original audit — 0:20 to 1:05

**Open:** original audit UI at `http://127.0.0.1:8000`.

**Action:**

1. Pause on the four summary numbers at the top.
2. Scroll slowly until the red `P-014` card fills most of the screen.
3. Pause on the `audit_events has 1284 row(s)` line.
4. Continue down just enough to show `P-021` and `P-031`.

**Say:**

> This audit checked three documents and created nine promises. P-014 is the deletion promise. The deletion job omits audit events, the database contains 1,284 expired audit-event rows, and the configured backup period is too long. Residency is also violated because the system uses us-east-1. The subprocessor promise is marked unverifiable because there is no authoritative source; Promise Ledger does not fabricate a pass.

### Scene 3 — Safe recovery from tool failure — 1:05 to 1:35

**Start on:** the green `P-017` card on the original audit UI.

**Point out:**

- `P-017` says **HOLDS**.
- The evidence line says `Recovered after PermissionError: AccessDenied`.
- The effective evidence says configured retention is 30 days.

**Then switch to:** the original Neatlogs trace.

**Action in Neatlogs:** show the trace overview and the span list. If finding an individual fallback span takes too long, keep the overview visible; do not waste recording time searching.

**Say:**

> The primary cloud snapshot check returned AccessDenied. That is a tool error, not proof of a contract violation. Promise Ledger records the error and follows the probe's declared Terraform fallback. Terraform proves 30-day retention, so the final verdict holds. Neatlogs preserves that execution path.

### Scene 4 — Fix and verify — 1:35 to 2:10

**Open in sequence:**

1. Tasklane PR #1.
2. Tasklane PR #2.
3. Fixed-result UI at `http://127.0.0.1:8001`.

**Action:**

1. On PR #1, show the title and the changed code adding `audit_events`. Do not review every line.
2. On PR #2, show the title and the Terraform value changing from 90 to 30.
3. On the fixed-result UI, scroll to `P-014` and pause on the green **HOLDS** label and the passing evidence rows.
4. Briefly show that `P-021` is still red and `P-031` is still unverifiable.

**Say:**

> The two independent causes become two small pull requests. The first includes audit events in tenant deletion. The second caps backup expiry at 30 days. We applied both in an isolated checkout, reran the purge and checks, and P-014 turned green. Residency and missing subprocessor evidence stayed unresolved, proving the re-check did not hide other failures.

### Scene 5 — Agent reliability — 2:10 to 2:35

**Open:** benchmark Neatlogs trace. If it is slow, open `evidence/benchmark.md` instead.

**Show:** v1 has 3 mismatches and v2 has 0.

**Then open:** `evidence/entire.md` and pause on the table row for `purge_expired_tenants`.

**Say:**

> A naive compiler mislabels three of ten seeded cases. It mistakes missing evidence for success and treats an access error as a violation. The grounded compiler makes zero of those mistakes. Entire Graph also finds the exact purge function from the contract language, rather than relying on a hard-coded file list.

### Scene 6 — Business viability — 2:35 to 3:00

**Open:** cfo.ai scenario model. If it is slow, show `evidence/cfo_scenario_model.png`.

**Point out:** the Base scenario and its approximately 76% gross margin.

**Then open:** the first page of `docs/business_plan.pdf` for two or three seconds.

**Finish on:** the top of the original audit UI, showing **Every promise gets a chain of proof**.

**Say:**

> The audit used about 3.8 thousand tokens across three model calls, roughly 1.7 cents under the model-price assumption. The base scenario prices monitored contracts at 39 dollars per month and reaches about 76 percent gross margin. Promise Ledger makes contract truth testable, fixable, and economically practical. Every promise gets a chain of proof.

Wait one second, then stop recording from the macOS menu-bar stop button.

## 6. Do we run the audit during recording?

No. The video shows completed, verified runs.

- `run_live_audit.json` is the original failing audit used by the UI on port `8000`.
- `run_remediated.json` is the isolated after-fix verification used by the UI on port `8001`.
- Neatlogs contains the original audit and benchmark traces.
- The two pull requests remain open and unmerged.

We may perform one fresh audit **before** recording to confirm reproducibility, but that is preparation I will handle. It should not appear in the three-minute video because model calls and network dashboards can be slow or fail unpredictably.

## 7. If something does not open

- If `8000` or `8001` fails: tell me which address failed. I will restart it; you do not need to use Terminal.
- If Neatlogs is slow: use `evidence/benchmark.md` for the benchmark and keep `P-017` visible in the local UI for recovery proof.
- If cfo.ai is slow or logged out: use `evidence/cfo_scenario_model.png`.
- If a GitHub PR asks you to sign in: use the Chrome profile already signed into `khushalkumar`.
- Never enter or display API keys during recording.

## 8. After recording

Play the video once and confirm:

- your voice is audible;
- no notification or secret appeared;
- `P-014` is visibly red before the fixes and green afterward;
- the video is close to three minutes;
- the final frame says **Every promise gets a chain of proof**.

Do not publish the video, repositories, or X posts until the final submission switch is explicitly approved.
