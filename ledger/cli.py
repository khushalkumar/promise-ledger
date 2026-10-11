import json
import os
from pathlib import Path
from typing import Annotated

import typer

from ledger.agents.extractor import extract_promises
from ledger.benchmark import compare_compilers
from ledger.documents import load_document
from ledger.llm import AzureJsonBackend
from ledger.models import LedgerRun, Promise, RunMetrics
from ledger.orchestrator import run_ledger
from ledger.probes.executors import ProbeContext
from ledger.registry import assign_canonical_ids, load_registry
from ledger.tracing import finish_tracing, initialize_tracing

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
        ledger_run = run_ledger(promises, ProbeContext(target_root=target, database=database))
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
