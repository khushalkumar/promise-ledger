# Promise Ledger demo recording guide

This guide assumes you have never seen the project before. You do not need to understand the code, JSON, credentials, or terminal setup. Before recording, I will prepare the browser tabs, local pages, and a Terminal window containing one safe command. During the recording, you press **Enter once** to run the real audit.

The demo is not a slideshow of old results. It contains one real end-to-end Promise Ledger execution. Saved traces and before/after results support that live execution.

## 1. What the hackathon requires

The live [neatHack page](https://neatlogs.com/hackathon) says the project must complete a substantial task from start to finish. The three-minute-or-shorter video must explicitly cover neatlogs, Entire, and cfo.ai, including architecture, implementation, runtime, reasoning, and result.

Our video therefore contains:

1. A real Promise Ledger audit started during the recording.
2. The resulting contractual verdicts.
3. A Neatlogs runtime trace and recovery path.
4. Entire Graph locating relevant implementation code.
5. Proposed fixes and a verified after-fix audit.
6. The cfo.ai business model and result.

## 2. What Promise Ledger does

Promise Ledger reads agreements, converts their clauses into named promises, checks those promises against a fictional SaaS called Tasklane, and preserves the evidence for every verdict.

The main example is `P-014`. `P-014` is an internal promise ID, not a priority or ticket number. It represents this clause from the fictional Northwind contract:

> Tasklane will delete Northwind's customer personal data within 30 days, including application records, audit events, exports, attachments, and backups.

The original audit marks `P-014` as **violated**. Applying the two runtime-created PR commits in an isolated checkout makes it **hold**.

## 3. What is live and what is saved

### Live during the video

- You press **Enter** in the prepared Terminal window.
- Promise Ledger reads the three documents, extracts nine promises, inventories Tasklane, runs code/database/Terraform checks, calculates verdicts, and sends runtime spans to Neatlogs.
- The Terminal prints the nine verdicts when the run finishes.
- We show the audit result and Neatlogs runtime.

The live audit normally takes approximately 15–30 seconds. Do not type any credentials. They will already be loaded outside the visible command.

### Saved supporting evidence

- The previously verified baseline protects us if a live external service is slow.
- The remediated audit proves the combined effect of the two runtime-created PR commits.
- The live compiler benchmark measures accuracy, tokens, latency, and estimated cost without replaying saved predictions.
- The Entire checkpoint proves AI-assisted work was captured during the hackathon.
- The cfo.ai workbook and business plan preserve the financial result.

## 4. Where everything is

| What | Where to open it | What you should see |
| --- | --- | --- |
| Northwind demo contract | [`contracts/Northwind_DPA_v3.pdf`](../contracts/Northwind_DPA_v3.pdf) | A one-page PDF titled **Northwind Data Processing Addendum**. Section 7.2 contains the 30-day deletion promise. |
| Prepared live-run Terminal | I will open this immediately before recording | One command waiting at the prompt. You press **Enter once**. No credential values will be visible. |
| Baseline audit UI | <http://127.0.0.1:8000> | Promise Ledger page. `P-014` is red and says **VIOLATED**. This is also the fallback if the live run is delayed. |
| Live result UI | <http://127.0.0.1:8002> | The result created while recording. I will prepare this address to display the new run after it finishes. |
| Neatlogs trace list | [Promise Ledger traces](https://app.neatlogs.com/traces?orgId=5d26aec1-b6b1-4572-b322-3f0ad165c998&projectId=61db443d-602a-484c-9136-1ae03eb5ae03) | The newest Promise Ledger run should appear first after refreshing. |
| Verified Neatlogs fallback | [Trace `279e...c551`](https://app.neatlogs.com/traces/279e6c54faac9ee0a38d05177481c551?orgId=5d26aec1-b6b1-4572-b322-3f0ad165c998&projectId=61db443d-602a-484c-9136-1ae03eb5ae03) | A 37-span run showing workflow, agents, tools, guardrails, input, and output. Use this if the fresh trace has not appeared yet. |
| Tasklane fix 1 | [Tasklane PR #3](https://github.com/khushalkumar/tasklane-demo/pull/3) | Runtime-created normal PR adding `audit_events` to the deletion job. Its checks pass. |
| Tasklane fix 2 | [Tasklane PR #4](https://github.com/khushalkumar/tasklane-demo/pull/4) | Runtime-created normal PR changing backup expiry from 90 days to 30 days. Its checks pass. |
| Fixed-result UI | <http://127.0.0.1:8001> | The isolated after-fix result. `P-014` is green and says **HOLDS**. |
| Autonomous run | [`evidence/run_autonomous.json`](../evidence/run_autonomous.json) | Run `pl-20261011T130117Z-6f374997`: two grounded causes, PRs #3/#4, and combined selective re-check. |
| Benchmark trace | [Trace `861b...bf5f`](https://app.neatlogs.com/traces/861bcfead02ad6de99ff5b7a0009bf5f?orgId=5d26aec1-b6b1-4572-b322-3f0ad165c998&projectId=61db443d-602a-484c-9136-1ae03eb5ae03) | Free-form v1 misses 8/10; grounded v2 gets 10/10 with 68% lower estimated model cost. |
| Benchmark backup | [`evidence/benchmark.md`](../evidence/benchmark.md) | The independent compiler comparison, including tokens, cost, latency, and repair-call data. |
| Entire evidence | [`evidence/entire.md`](../evidence/entire.md) | Entire Graph finds `purge_expired_tenants` in `tasklane/jobs/purge_tenant.py`; the checkpoint ID is also recorded. |
| cfo.ai model | [Promise Ledger scenario page](https://app.cfo.ai/outgoing-sheep-2dce4103/chat/ff58a708-efba-45ab-adce-dcf04fd52383?pageId=e21c5cbf-b709-43da-a9cd-9c7be1769de2&panel=page&scenario=9e525b60-f4d7-4c9f-aef4-6101c66d1453) | Downside, Base, and Growth financial scenarios. |
| cfo.ai backup image | [`evidence/cfo_scenario_model.png`](../evidence/cfo_scenario_model.png) | Static scenario table if the live page is slow. |
| Business plan | [`docs/business_plan.pdf`](business_plan.pdf) | Four-page **Promise Ledger - Business Plan**. |

The `127.0.0.1` addresses are pages running on this Mac, not public websites. I will confirm all three addresses before recording.

## 5. What the audit page means

At the top:

- **Red signals: 3** means two violated system promises plus one document conflict.
- **Promises: 9** means nine contractual obligations were extracted.
- **Source documents: 3** means two generated contracts and one policy were checked.
- **Unverifiable: 1** means one promise lacked an authoritative evidence source. The system refused to invent a pass or failure.

Important promise cards:

- `P-014` — deletion within 30 days. Red because deletion code omits a table, expired rows remain, and backup retention is 90 rather than 30 days.
- `P-017` — database snapshot retention. Green because a cloud permission failure safely falls back to Terraform evidence.
- `P-021` — EU data residency. Red because the system uses `us-east-1`, not the promised `eu-west-1`.
- `P-031` — subprocessor notice. Unverifiable because no authoritative evidence source exists.

## 6. Before recording

Do not start recording until I confirm: **“The live-run Terminal and all demo tabs are ready.”**

I will prepare these tabs in order:

1. Northwind contract PDF.
2. Prepared live-run Terminal.
3. Live result UI (`8002`).
4. Baseline audit UI (`8000`) as a fallback.
5. Neatlogs trace list and verified trace.
6. Entire evidence.
7. Tasklane PR #3.
8. Tasklane PR #4.
9. Fixed-result UI (`8001`).
10. cfo.ai scenario model and backup image.
11. Business-plan PDF.

I will also run one rehearsal before the final take. The rehearsal verifies execution time, the live result page, and trace delivery. It is not the submitted recording.

Close unrelated tabs and hide bookmarks, notifications, email, Slack, and anything containing credentials. Keep both Tasklane pull requests unmerged.

### Start macOS recording

1. Press `Shift-Command-5`.
2. Select **Record Entire Screen**.
3. Click **Options**.
4. Under **Microphone**, select the microphone you will speak into.
5. Under **Save to**, select Desktop or another known folder.
6. Turn off **Show Mouse Clicks** unless you want click circles.
7. Click **Record**.
8. Wait two seconds before speaking.

## 7. The six scenes, click by click

### Scene 1 — Goal and contract — 0:00 to 0:15

**Open:** `contracts/Northwind_DPA_v3.pdf`.

**Show:** section **7.2 Deletion and backup retention**.

**Say:**

> Promise Ledger is an agent that turns contractual promises into checks against code, data, and infrastructure. This fictional contract requires Tasklane to delete customer data and backups within 30 days.

### Scene 2 — Run the agent live — 0:15 to 0:45

**Open:** the prepared Terminal.

**Action:** press **Enter once**. Do not type anything else. The command will visibly name the three contract or policy files and the Tasklane target. Wait for the verdict list.

**Expected output:** nine rows such as `P-014 violated`, `P-017 holds`, and `P-031 unverifiable`, followed by the document conflict.

**Say while it runs:**

> This is a real audit. The agent reads three documents, assigns stable promise IDs, inventories the Tasklane repository and database, compiles grounded checks, executes them, handles fallbacks, and calculates the verdicts. The same run is being traced in Neatlogs.

If it takes longer than 30 seconds, stop waiting and switch to the baseline UI at `8000`. The saved trace remains valid evidence; do not leave a blank Terminal on screen.

### Scene 3 — Reasoning and result — 0:45 to 1:15

**Open:** the live result UI at `8002`. If it is not ready, use baseline UI `8000`.

**Action:**

1. Show the four summary numbers.
2. Scroll to red `P-014`.
3. Pause on `audit_events has 1284 row(s)` and `configured retention is 90 days; contract maximum is 30`.
4. Move to green `P-017` and show `Recovered after PermissionError: AccessDenied`.

**Say:**

> P-014 fails across code, data, and configuration: the deletion job omits audit events, 1,284 expired audit-event rows remain, and backup retention is 90 days instead of 30. P-017 demonstrates recovery. AccessDenied is recorded as a tool error, then the declared Terraform fallback proves compliant retention, so the verdict holds.

### Scene 4 — neatlogs and Entire runtime — 1:15 to 1:50

**Open:** the Neatlogs trace list, refresh, and select the newest Promise Ledger run. If it has not appeared, use verified trace `279e...c551`.

**Show:** the `ledger_run` workflow and its nested agent, tool, and guardrail spans.

**Then open:** `evidence/entire.md` and pause on `purge_expired_tenants`.

**Say:**

> The implementation wraps the audit as a Neatlogs workflow with extraction and compilation agents, inventory and probe tools, and verdict guardrails. The runtime preserves inputs, outputs, latency, tokens, failures, and fallback reasoning. During inventory, Entire Graph searches repository context and finds the exact purge function responsible for deletion. Entire also preserves the AI-change checkpoint behind the implementation.

This explicitly covers neatlogs architecture, implementation, runtime, reasoning, and result, plus Entire implementation and runtime result.

### Scene 5 — Fix and verify — 1:50 to 2:25

**Open in sequence:** Tasklane PR #3, PR #4, then fixed-result UI `8001`.

**Action:**

1. On PR #3, show the title, green checks, runtime run ID, and `audit_events` added to deletion.
2. On PR #4, show the title, green checks, runtime run ID, and backup expiry changing from 90 to 30.
3. On `8001`, show green `P-014` and its passing checks.
4. Briefly show that `P-021` remains red and `P-031` remains unverifiable.

**Say:**

> The autonomous run created these two normal, reviewable pull requests—one for tenant deletion and one for backup expiry. Both have passing checks and AI-change checkpoints. The agent then combined their exact commits in an isolated checkout and selectively rechecked the affected evidence. P-014 turns green, while residency and missing subprocessor evidence remain unresolved.

### Scene 6 — cfo.ai and conclusion — 2:25 to 3:00

**Open:** the cfo.ai scenario model. Use `evidence/cfo_scenario_model.png` if the page is slow.

**Show:** the Base scenario: 200 monitored contracts, `$39` monthly price, and approximately `75.84%` gross margin.

**Then show:** the first page of `docs/business_plan.pdf` for two seconds and finish at the top of the Promise Ledger UI.

**Say:**

> cfo.ai turns measured runtime usage—about 3.8 thousand tokens and roughly 1.7 cents per audit—into pricing, revenue, cost, margin, and runway scenarios. The base model prices monitoring at 39 dollars per contract per month and reaches about 76 percent gross margin. That model and the resulting business plan are included in the repository. Promise Ledger makes contract truth testable, fixable, and economically practical. Every promise gets a chain of proof.

Wait one second, then stop recording from the macOS menu-bar stop button.

## 8. If something fails during recording

- **Live audit exceeds 30 seconds:** switch to `8000` and continue. Do not restart it on camera.
- **Live result page `8002` is unavailable:** use baseline `8000`.
- **Fresh Neatlogs trace is delayed:** use verified trace `279e...c551`.
- **Neatlogs itself is slow:** show the local `P-017` recovery result and `evidence/benchmark.md`.
- **cfo.ai is slow or logged out:** use `evidence/cfo_scenario_model.png`.
- **GitHub asks for sign-in:** use the Chrome profile already signed into `khushalkumar`.
- **Any secret appears:** stop recording immediately and discard that take.

The fallback material is supporting evidence, but every final take should begin with the real live audit attempt.

## 9. After recording

Play the entire video once and confirm:

- the live audit command is visibly started;
- the Terminal shows real verdict output or the 30-second fallback transition is clear;
- your voice is audible;
- no credentials, notifications, or private unrelated information appear;
- neatlogs, Entire, and cfo.ai are each explicitly explained;
- `P-014` is visibly red before the fixes and green afterward;
- the duration is three minutes or less;
- the final frame says **Every promise gets a chain of proof**.

Do not publish the video, repositories, or X post until the final submission switch is explicitly approved.
