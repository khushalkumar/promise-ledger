from __future__ import annotations

import json
from collections import Counter
from time import perf_counter
from typing import Protocol

import neatlogs
from pydantic import BaseModel

from ledger.agents.compiler_agent import compile_checks_with_agent
from ledger.models import AssetMap, LedgerRun, Probe, Promise, PromiseKind, SourceSpan, Verdict
from ledger.orchestrator import run_ledger
from ledger.probes.executors import ProbeContext
from ledger.tracing import current_trace_id

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


class JsonBackend(Protocol):
    def complete_json(self, system: str, user: str) -> str: ...


class FreeformProbePlan(BaseModel):
    probes: list[Probe]
    reasoning: str


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
    llm_calls: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    estimated_cost_usd: float


class BenchmarkResult(BaseModel):
    trace_id: str | None = None
    cases: int
    v1: CompilerMetrics
    v2: CompilerMetrics
    details: list[BenchmarkCase]


V1_SYSTEM_PROMPT = """You are the Promise Ledger v1 free-form check compiler.
Create a safe probe plan from the written promise, available system assets, and supported template
signatures. Unlike v2, you receive no deterministic candidate probes and must independently choose
templates, parameters, dependencies, and fallbacks. Never invent an asset that is not in the
inventory. Return JSON matching the supplied schema.
"""


@neatlogs.span(kind="AGENT", name="compiler_v1_freeform")
def _v1_compile(promise: Promise, assets: AssetMap, backend: JsonBackend) -> list[Probe]:
    payload = {
        "promise": promise.model_dump(mode="json"),
        "system_inventory": assets.model_dump(mode="json"),
        "supported_templates": {
            "sql.no_rows_after_deadline": ["table", "deadline_days", "now"],
            "static.purge_covers_tables": ["path", "required_tables"],
            "terraform.maximum_retention": ["path", "maximum_days", "attribute?"],
            "terraform.allowed_regions": ["path", "allowed_regions"],
            "terraform.attribute_equals": ["path", "attribute", "expected"],
            "json.value_equals": ["path", "key_path", "expected"],
            "json.value_at_least": ["path", "key_path", "minimum"],
            "cloud.backup_retention": ["response", "retention_days?", "maximum_days"],
        },
        "response_schema": FreeformProbePlan.model_json_schema(),
    }
    plan = FreeformProbePlan.model_validate_json(
        backend.complete_json(V1_SYSTEM_PROMPT, json.dumps(payload, indent=2))
    )
    return _normalize_freeform_probes(promise, assets, plan.probes)


def _normalize_freeform_probes(
    promise: Promise,
    assets: AssetMap,
    probes: list[Probe],
) -> list[Probe]:
    allowed_templates = {
        "sql.no_rows_after_deadline",
        "static.purge_covers_tables",
        "terraform.maximum_retention",
        "terraform.allowed_regions",
        "terraform.attribute_equals",
        "json.value_equals",
        "json.value_at_least",
        "cloud.backup_retention",
    }
    allowed_paths = {*assets.source_files, *assets.terraform_files, *assets.config_files}
    sequence = 0

    def normalize(probe: Probe) -> Probe:
        nonlocal sequence
        sequence += 1
        current = sequence
        if probe.template not in allowed_templates:
            raise ValueError(f"v1 emitted unsupported probe template: {probe.template}")
        path = probe.params.get("path")
        if path is not None and path not in allowed_paths:
            raise ValueError(f"v1 emitted ungrounded path: {path}")
        table = probe.params.get("table")
        if table is not None and table not in assets.tenant_tables:
            raise ValueError(f"v1 emitted ungrounded table: {table}")
        fallback = normalize(probe.fallback) if probe.fallback is not None else None
        dependency_allowlist = allowed_paths | set(assets.tenant_tables)
        dependencies = [item for item in probe.depends_on if item in dependency_allowlist]
        slug = probe.template.replace(".", "-")
        return probe.model_copy(
            update={
                "id": f"{promise.id}-v1-{current}-{slug}",
                "depends_on": dependencies,
                "fallback": fallback,
            }
        )

    return [normalize(probe) for probe in probes]


@neatlogs.span(kind="WORKFLOW", name="compiler_benchmark")
def compare_compilers(
    baseline: LedgerRun,
    context: ProbeContext,
    *,
    v1_backend: JsonBackend,
    v2_backend: JsonBackend,
    input_cost_per_million: float = 2.5,
    output_cost_per_million: float = 10.0,
) -> BenchmarkResult:
    reports = {report.promise.id: report for report in baseline.reports}
    unknown = sorted(set(reports) - set(EXPECTED_VERDICTS))
    if unknown:
        raise ValueError(f"Benchmark has no expected verdict for: {', '.join(unknown)}")

    promises = [report.promise for report in baseline.reports]
    if "P-050" not in reports:
        promises.append(_unsupported_promise())

    v1_before = _usage_snapshot(v1_backend)
    v1_started = perf_counter()
    freeform = run_ledger(
        promises,
        context,
        compiler=lambda promise, assets: _v1_compile(promise, assets, v1_backend),
    )
    v1_elapsed = (perf_counter() - v1_started) * 1000
    v1_predictions = {report.promise.id: report.verdict for report in freeform.reports}

    v2_before = _usage_snapshot(v2_backend)
    v2_started = perf_counter()
    grounded = run_ledger(
        promises,
        context,
        compiler=lambda promise, assets: compile_checks_with_agent(
            promise,
            assets,
            v2_backend,
        ).probes,
    )
    v2_elapsed = (perf_counter() - v2_started) * 1000
    v2_predictions = {report.promise.id: report.verdict for report in grounded.reports}

    details = [
        BenchmarkCase(
            promise_id=promise.id,
            expected=EXPECTED_VERDICTS[promise.id],
            v1=v1_predictions[promise.id],
            v2=v2_predictions[promise.id],
        )
        for promise in promises
    ]
    return BenchmarkResult(
        trace_id=current_trace_id(),
        cases=len(details),
        v1=_metrics(
            details,
            "v1",
            _usage_delta(v1_backend, v1_before, fallback_calls=len(promises)),
            v1_elapsed,
            input_cost_per_million,
            output_cost_per_million,
        ),
        v2=_metrics(
            details,
            "v2",
            _usage_delta(v2_backend, v2_before, fallback_calls=len(promises)),
            v2_elapsed,
            input_cost_per_million,
            output_cost_per_million,
        ),
        details=details,
    )


def _unsupported_promise() -> Promise:
    return Promise(
        id="P-050",
        kind=PromiseKind.NOTICE_PERIOD,
        actor="Tasklane",
        object="material service changes",
        deadline_days=45,
        source=SourceSpan(
            document="benchmark_unsupported_clause.md",
            clause="1",
            text="Tasklane will give 45 days notice before a material service change.",
        ),
    )


def _usage_snapshot(backend: JsonBackend) -> tuple[int, int, int, int]:
    usage = getattr(backend, "usage", None)
    return (
        int(getattr(usage, "calls", 0)),
        int(getattr(usage, "prompt_tokens", 0)),
        int(getattr(usage, "completion_tokens", 0)),
        int(getattr(usage, "total_tokens", 0)),
    )


def _usage_delta(
    backend: JsonBackend,
    before: tuple[int, int, int, int],
    *,
    fallback_calls: int,
) -> tuple[int, int, int, int]:
    after = _usage_snapshot(backend)
    delta = tuple(end - start for start, end in zip(before, after, strict=True))
    if delta == (0, 0, 0, 0):
        return fallback_calls, 0, 0, 0
    return delta


def _metrics(
    details: list[BenchmarkCase],
    field: str,
    usage: tuple[int, int, int, int],
    latency_ms: float,
    input_cost_per_million: float,
    output_cost_per_million: float,
) -> CompilerMetrics:
    predictions = [getattr(case, field) for case in details]
    counts = Counter(predictions)
    pairs = list(zip(details, predictions, strict=True))
    calls, prompt_tokens, completion_tokens, total_tokens = usage
    estimated_cost = (
        prompt_tokens * input_cost_per_million
        + completion_tokens * output_cost_per_million
    ) / 1_000_000
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
        llm_calls=calls,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        latency_ms=round(latency_ms, 3),
        estimated_cost_usd=round(estimated_cost, 6),
    )
