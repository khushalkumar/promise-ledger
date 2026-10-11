import json
import os
from pathlib import Path
from typing import Annotated

import typer

from ledger.models import Promise
from ledger.orchestrator import run_ledger
from ledger.probes.executors import ProbeContext
from ledger.tracing import finish_tracing, initialize_tracing

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Check contractual promises against a target system."""


@app.command("run")
def run_command(
    target: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    database: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
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
    finally:
        finish_tracing(tracing_enabled)
