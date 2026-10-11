import json
from pathlib import Path

from ledger import benchmark as benchmark_module
from ledger.benchmark import compare_compilers, v1_verdict
from ledger.models import LedgerRun, Verdict

REPOSITORY_ROOT = Path(__file__).parents[1]


def live_run() -> LedgerRun:
    return LedgerRun.model_validate_json(
        (REPOSITORY_ROOT / "evidence" / "run_live_audit.json").read_text()
    )


def test_v1_mislabels_access_denied_when_fallback_passes():
    report = next(
        report for report in live_run().reports if report.promise.id == "P-017"
    )

    assert v1_verdict(report) is Verdict.VIOLATED
    assert report.verdict is Verdict.HOLDS


def test_benchmark_shows_grounded_compiler_eliminates_seeded_mismatches():
    benchmark = compare_compilers(live_run())

    assert benchmark.cases == 10
    assert benchmark.v1.mismatches == 3
    assert benchmark.v1.false_violations == 1
    assert benchmark.v1.false_holds == 2
    assert benchmark.v2.mismatches == 0
    assert benchmark.v2.false_violations == 0
    assert benchmark.v2.false_holds == 0
    serialized = json.loads(benchmark.model_dump_json())
    assert serialized["v2"]["unverifiable"] == 2


def test_benchmark_keeps_the_active_neatlogs_trace_id(monkeypatch):
    trace_id = "abcdef0123456789abcdef0123456789"
    monkeypatch.setattr(benchmark_module, "current_trace_id", lambda: trace_id)

    benchmark = compare_compilers(live_run())

    assert benchmark.trace_id == trace_id
