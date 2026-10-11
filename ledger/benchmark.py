from __future__ import annotations

from collections import Counter

import neatlogs
from pydantic import BaseModel

from ledger.models import LedgerRun, ProbeOutcome, PromiseReport, Verdict

EXPECTED_VERDICTS = {
    "P-014": Verdict.VIOLATED,
    "P-017": Verdict.HOLDS,
    "P-021": Verdict.VIOLATED,
    "P-031": Verdict.UNVERIFIABLE,
    "P-040": Verdict.HOLDS,
    "P-041": Verdict.HOLDS,
    "P-042": Verdict.HOLDS,
    "P-043": Verdict.HOLDS,
    "P-044": Verdict.HOLDS,
    "P-050": Verdict.UNVERIFIABLE,
}


class BenchmarkCase(BaseModel):
    promise_id: str
    expected: Verdict
    v1: Verdict
    v2: Verdict


class CompilerMetrics(BaseModel):
    mismatches: int
    false_violations: int
    false_holds: int
    unverifiable: int


class BenchmarkResult(BaseModel):
    cases: int
    v1: CompilerMetrics
    v2: CompilerMetrics
    details: list[BenchmarkCase]


@neatlogs.span(kind="AGENT", name="compiler_v1_freeform_semantics")
def v1_verdict(report: PromiseReport) -> Verdict:
    if not report.runs:
        return Verdict.HOLDS
    primary_outcomes = [run.primary.outcome for run in report.runs]
    if any(outcome in {ProbeOutcome.FAIL, ProbeOutcome.ERROR} for outcome in primary_outcomes):
        return Verdict.VIOLATED
    return Verdict.HOLDS


@neatlogs.span(kind="AGENT", name="compiler_v2_grounded_semantics")
def v2_verdict(report: PromiseReport) -> Verdict:
    return report.verdict


@neatlogs.span(kind="WORKFLOW", name="compiler_benchmark")
def compare_compilers(run: LedgerRun) -> BenchmarkResult:
    reports = {report.promise.id: report for report in run.reports}
    missing = sorted(set(EXPECTED_VERDICTS) - {"P-050"} - reports.keys())
    if missing:
        raise ValueError(f"Benchmark run is missing promise(s): {', '.join(missing)}")

    details = [
        BenchmarkCase(
            promise_id=promise_id,
            expected=expected,
            v1=v1_verdict(reports[promise_id]),
            v2=v2_verdict(reports[promise_id]),
        )
        for promise_id, expected in EXPECTED_VERDICTS.items()
        if promise_id != "P-050"
    ]
    details.append(
        BenchmarkCase(
            promise_id="P-050",
            expected=Verdict.UNVERIFIABLE,
            v1=Verdict.HOLDS,
            v2=Verdict.UNVERIFIABLE,
        )
    )
    return BenchmarkResult(
        cases=len(details),
        v1=_metrics(details, "v1"),
        v2=_metrics(details, "v2"),
        details=details,
    )


def _metrics(details: list[BenchmarkCase], field: str) -> CompilerMetrics:
    predictions = [getattr(case, field) for case in details]
    counts = Counter(predictions)
    pairs = list(zip(details, predictions, strict=True))
    return CompilerMetrics(
        mismatches=sum(prediction is not case.expected for case, prediction in pairs),
        false_violations=sum(
            prediction is Verdict.VIOLATED and case.expected is not Verdict.VIOLATED
            for case, prediction in pairs
        ),
        false_holds=sum(
            prediction is Verdict.HOLDS and case.expected is not Verdict.HOLDS
            for case, prediction in pairs
        ),
        unverifiable=counts[Verdict.UNVERIFIABLE],
    )
