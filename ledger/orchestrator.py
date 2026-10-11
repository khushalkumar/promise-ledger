import json
from collections.abc import Callable, Sequence

import neatlogs

from ledger.agents.compiler import compile_checks
from ledger.conflicts import detect_conflicts
from ledger.inventory import build_inventory
from ledger.models import AssetMap, LedgerRun, Probe, Promise, PromiseReport
from ledger.probes.executors import ProbeContext, execute_probe
from ledger.probes.runner import run_probe
from ledger.verdict import evaluate_verdict

CheckCompiler = Callable[[Promise, AssetMap], list[Probe]]


def run_ledger(
    promises: Sequence[Promise],
    context: ProbeContext,
    *,
    compiler: CheckCompiler = compile_checks,
) -> LedgerRun:
    with neatlogs.trace(name="ledger_run", kind="WORKFLOW") as span:
        span.set_attribute(
            "input.value",
            json.dumps(
                {
                    "promises": [promise.model_dump(mode="json") for promise in promises],
                    "target_root": str(context.target_root),
                    "database": str(context.database),
                }
            ),
        )
        span.set_attribute("input.mime_type", "application/json")
        ledger_run = _run_ledger(promises, context, compiler=compiler)
        span.set_attribute("output.value", ledger_run.model_dump_json())
        span.set_attribute("output.mime_type", "application/json")
        return ledger_run


def _run_ledger(
    promises: Sequence[Promise],
    context: ProbeContext,
    *,
    compiler: CheckCompiler = compile_checks,
) -> LedgerRun:
    graph_query = " ".join(
        [
            "contract compliance",
            *(
                f"{promise.kind} {promise.object} {' '.join(promise.includes)} "
                f"{promise.source.text}"
                for promise in promises
            ),
        ]
    )[:1000]
    assets = build_inventory(context, graph_query=graph_query)
    reports = []
    for promise in promises:
        probes = compiler(promise, assets)
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
    return LedgerRun(
        reports=reports,
        conflicts=detect_conflicts(promises),
        inventory=assets,
    )


@neatlogs.span(kind="WORKFLOW", name="selective_recheck")
def recheck_ledger(
    baseline: LedgerRun,
    context: ProbeContext,
    *,
    affected_probe_ids: Sequence[str],
) -> LedgerRun:
    affected = set(affected_probe_ids)
    promises = [report.promise for report in baseline.reports]
    graph_query = " ".join(
        f"{promise.kind} {promise.object} {promise.source.text}" for promise in promises
    )[:1000]
    assets = build_inventory(context, graph_query=graph_query)
    reports = []
    for previous_report in baseline.reports:
        probes = compile_checks(previous_report.promise, assets)
        previous_runs = {
            run.primary.probe_id: run for run in previous_report.runs
        }
        runs = []
        for probe in probes:
            previous = previous_runs.get(probe.id)
            if probe.id in affected or previous is None:
                runs.append(
                    run_probe(probe, lambda item: execute_probe(item, context))
                )
            else:
                runs.append(previous)
        reports.append(
            PromiseReport(
                promise=previous_report.promise,
                probes=probes,
                runs=runs,
                verdict=evaluate_verdict([run.effective_result for run in runs]),
            )
        )
    return LedgerRun(
        reports=reports,
        conflicts=detect_conflicts(promises),
        metrics=baseline.metrics,
        inventory=assets,
    )
