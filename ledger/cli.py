import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import typer

from ledger.agents.compiler_agent import compile_checks_with_agent
from ledger.agents.extractor import extract_promises
from ledger.agents.investigator import EvidenceInvestigator
from ledger.agents.remediator import RemediationAgent
from ledger.benchmark import compare_compilers
from ledger.documents import load_document
from ledger.integrations.codex import CodexCodingAgent
from ledger.integrations.github import GhPullRequests
from ledger.integrations.recheck import ConfiguredRechecker
from ledger.integrations.workspace import GitWorkspace
from ledger.llm import AzureJsonBackend
from ledger.models import LedgerRun, Promise, RunMetrics
from ledger.orchestrator import run_ledger
from ledger.probes.executors import ProbeContext
from ledger.registry import assign_canonical_ids, load_registry
from ledger.store import RunStore
from ledger.tracing import finish_tracing, initialize_tracing
from ledger.workflow import AutonomousWorkflow

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Check contractual promises against a target system."""


def _extract_documents(document: list[Path], backend: AzureJsonBackend) -> list[Promise]:
    promises: list[Promise] = []
    for path in document:
        promises.extend(
            extract_promises(
                load_document(path),
                backend,
                starting_index=len(promises) + 1,
            )
        )
    return promises


@app.command("extract")
def extract_command(
    document: Annotated[
        list[Path],
        typer.Option(exists=True, dir_okay=False, help="Contract or policy to extract"),
    ],
    output: Annotated[Path, typer.Option(dir_okay=False)],
) -> None:
    tracing_enabled = initialize_tracing(os.getenv("NEATLOGS_API_KEY"))
    try:
        backend = AzureJsonBackend.from_env()
        promises = _extract_documents(document, backend)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps([item.model_dump(mode="json") for item in promises], indent=2) + "\n"
        )
        typer.echo(f"Extracted {len(promises)} promises to {output}")
    finally:
        finish_tracing(tracing_enabled)


@app.command("audit")
def audit_command(
    target: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    database: Annotated[
        str,
        typer.Option(help="SQLite path or SQLAlchemy PostgreSQL URL"),
    ],
    document: Annotated[
        list[Path],
        typer.Option(exists=True, dir_okay=False, help="Contract or policy to audit"),
    ],
    registry: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option(dir_okay=False)],
) -> None:
    tracing_enabled = initialize_tracing(os.getenv("NEATLOGS_API_KEY"))
    try:
        backend = AzureJsonBackend.from_env()
        extracted = _extract_documents(document, backend)
        promises = assign_canonical_ids(extracted, load_registry(registry))
        ledger_run = run_ledger(
            promises,
            ProbeContext(target_root=target, database=database),
            compiler=lambda promise, assets: compile_checks_with_agent(
                promise, assets, backend
            ).probes,
        )
        usage = getattr(backend, "usage", None)
        ledger_run.metrics = RunMetrics(
            documents=len(document),
            promises=len(promises),
            llm_calls=getattr(usage, "calls", len(document)),
            prompt_tokens=getattr(usage, "prompt_tokens", 0),
            completion_tokens=getattr(usage, "completion_tokens", 0),
            total_tokens=getattr(usage, "total_tokens", 0),
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(ledger_run.model_dump_json(indent=2) + "\n")
        for report in ledger_run.reports:
            typer.echo(f"{report.promise.id}  {report.verdict}")
        for conflict in ledger_run.conflicts:
            typer.echo(f"{conflict.id}  {conflict.verdict}  {conflict.detail}")
    finally:
        finish_tracing(tracing_enabled)


@app.command("agent-run")
def agent_run_command(
    target: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    database: Annotated[
        str,
        typer.Option(help="SQLite path or SQLAlchemy PostgreSQL URL"),
    ],
    document: Annotated[
        list[Path],
        typer.Option(exists=True, dir_okay=False, help="Contract or policy to audit"),
    ],
    registry: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    repository: Annotated[
        str,
        typer.Option(help="GitHub owner/repository receiving remediation PRs"),
    ],
    state_database: Annotated[
        str,
        typer.Option(help="SQLAlchemy URL for durable workflow state"),
    ],
    worktree_root: Annotated[Path, typer.Option(file_okay=False)],
    output: Annotated[Path, typer.Option(dir_okay=False)],
) -> None:
    """Audit, remediate violations into real PRs, and recheck the combined commits."""
    tracing_enabled = initialize_tracing(os.getenv("NEATLOGS_API_KEY"))
    try:
        backend = AzureJsonBackend.from_env()
        extracted = _extract_documents(document, backend)
        promises = assign_canonical_ids(extracted, load_registry(registry))
        baseline = run_ledger(
            promises,
            ProbeContext(target_root=target, database=database),
            compiler=lambda promise, assets: compile_checks_with_agent(
                promise, assets, backend
            ).probes,
        )
        usage = getattr(backend, "usage", None)
        baseline.metrics = RunMetrics(
            documents=len(document),
            promises=len(promises),
            llm_calls=getattr(usage, "calls", len(document) + len(promises)),
            prompt_tokens=getattr(usage, "prompt_tokens", 0),
            completion_tokens=getattr(usage, "completion_tokens", 0),
            total_tokens=getattr(usage, "total_tokens", 0),
        )

        workflow = AutonomousWorkflow(
            store=RunStore(state_database),
            investigator=EvidenceInvestigator(target, backend),
            remediator=RemediationAgent(
                coding_agent=CodexCodingAgent(binary=os.getenv("CODEX_BINARY", "codex")),
                workspace=GitWorkspace(target, worktree_root / "remediations"),
                pull_requests=GhPullRequests(repository),
            ),
            rechecker=ConfiguredRechecker(target, worktree_root / "rechecks"),
        )
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        run_id = f"pl-{timestamp}-{uuid4().hex[:8]}"
        result = workflow.remediate(
            run_id=run_id,
            target_repository=repository,
            baseline=baseline,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result.model_dump_json(indent=2) + "\n")

        typer.echo(f"Run {run_id} completed")
        for remediation in result.remediations:
            typer.echo(f"PR {remediation.pull_request.url}")
        for report in result.rechecked.reports:
            typer.echo(f"{report.promise.id}  {report.verdict}")
    finally:
        finish_tracing(tracing_enabled)


@app.command("bench")
def bench_command(
    run: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option(dir_okay=False)],
) -> None:
    tracing_enabled = initialize_tracing(os.getenv("NEATLOGS_API_KEY"))
    try:
        benchmark = compare_compilers(LedgerRun.model_validate_json(run.read_text()))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(benchmark.model_dump_json(indent=2) + "\n")
        typer.echo(
            f"v1 mismatches={benchmark.v1.mismatches} "
            f"false_violations={benchmark.v1.false_violations} "
            f"false_holds={benchmark.v1.false_holds}"
        )
        typer.echo(
            f"v2 mismatches={benchmark.v2.mismatches} "
            f"false_violations={benchmark.v2.false_violations} "
            f"false_holds={benchmark.v2.false_holds}"
        )
    finally:
        finish_tracing(tracing_enabled)


@app.command("run")
def run_command(
    target: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    database: Annotated[
        str,
        typer.Option(help="SQLite path or SQLAlchemy PostgreSQL URL"),
    ],
    promises: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option(dir_okay=False)],
) -> None:
    tracing_enabled = initialize_tracing(os.getenv("NEATLOGS_API_KEY"))
    try:
        loaded_promises = [
            Promise.model_validate(item) for item in json.loads(promises.read_text())
        ]
        ledger_run = run_ledger(
            loaded_promises,
            ProbeContext(target_root=target, database=database),
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(ledger_run.model_dump_json(indent=2))

        for report in ledger_run.reports:
            typer.echo(f"{report.promise.id}  {report.verdict}")
        for conflict in ledger_run.conflicts:
            typer.echo(f"{conflict.id}  {conflict.verdict}  {conflict.detail}")
    finally:
        finish_tracing(tracing_enabled)
