# Build-in-public drafts

These are drafts for [@khushalkumar31](https://x.com/khushalkumar31). Do not publish without explicit approval. Add a real screenshot or short clip to every post and verify that no private repository details or credentials are visible.

## Draft 1 - The problem

Contracts promise outcomes. Evidence lives in code, tenant data, Terraform, cloud APIs, and public policies.

For #neatHack, team **el el ems** is building Promise Ledger: an agent that turns each clause into a chain of proof - source, check, evidence, verdict, and remediation.

## Draft 2 - First end-to-end run

First Promise Ledger run is live:

- 3 contract and policy documents
- 9 typed promises
- 2 system violations
- 1 cross-document conflict
- 1 honestly unverifiable promise

The headline finding: a 30-day deletion promise breaks across code, data, and backup config. #neatHack

## Draft 3 - Failure recovery

An `AccessDenied` is not proof that a contract is violated.

Promise Ledger records the cloud probe as an error, follows its declared Terraform fallback, proves 30-day snapshot retention, and returns `holds`.

Neatlogs makes the full `error -> fallback -> pass` path inspectable. #neatHack

## Draft 4 - Fix and re-check

One violated promise, two independent root causes, two reviewable PRs:

1. Purge the 1,284 missed `audit_events` rows.
2. Reduce backup expiry from 90 days to 30.

The combined re-check turns only the deletion promise green. Residency and the policy conflict stay red. That is the proof. #neatHack

## Draft 5 - Final build

Promise Ledger now runs contract -> typed promise -> grounded probe -> verdict -> PR -> re-check.

The live three-document audit uses about 3.8 thousand tokens across three model calls. Our cfo.ai-ready base model projects about 76% gross margin at 200 monitored contracts.

Every promise gets a chain of proof. #neatHack
