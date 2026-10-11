from collections.abc import Sequence

import neatlogs

from ledger.agents.compiler import compile_checks
from ledger.inventory import build_inventory
from ledger.models import LedgerRun, Promise, PromiseReport
from ledger.probes.executors import ProbeContext, execute_probe
from ledger.probes.runner import run_probe
from ledger.verdict import evaluate_verdict


@neatlogs.span(kind="WORKFLOW", name="ledger_run")
def run_ledger(promises: Sequence[Promise], context: ProbeContext) -> LedgerRun:
    assets = build_inventory(context)
    reports = []
    for promise in promises:
        probes = compile_checks(promise, assets)
        runs = [run_probe(probe, lambda item: execute_probe(item, context)) for probe in probes]
        verdict = evaluate_verdict([run.effective_result for run in runs])
        reports.append(
            PromiseReport(
                promise=promise,
                probes=probes,
                runs=runs,
                verdict=verdict,
            )
        )
    return LedgerRun(reports=reports)
