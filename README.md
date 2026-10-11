# Promise Ledger

Promise Ledger is an agentic contract-verification proof of concept built by team **el el ems** for neatHack 2026.

It turns contractual promises into deterministic checks, runs those checks against a target system, distinguishes violations from infrastructure errors, investigates failures, and prepares evidence-backed remediations.

## Status

Active hackathon build. The first end-to-end target is the fictional Tasklane SaaS application.

## Development

The project targets Python 3.12 and uses `uv`.

```bash
uv sync --all-groups
uv run pytest
```

Runtime credentials are supplied through environment variables and are never committed.

## Team

el el ems

