import hashlib
from collections.abc import Callable

import neatlogs

from ledger.models import Probe, ProbeOutcome, ProbeResult, ProbeRun
from ledger.tracing import current_trace_id

ProbeExecutor = Callable[[Probe], tuple[ProbeOutcome, str]]


@neatlogs.span(kind="TOOL", name="probe_runner")
def run_probe(probe: Probe, executor: ProbeExecutor) -> ProbeRun:
    primary = _execute(probe, executor)
    fallback = None
    if primary.outcome is ProbeOutcome.ERROR and probe.fallback is not None:
        fallback = _execute(probe.fallback, executor)
    return ProbeRun(primary=primary, fallback=fallback)


def _execute(probe: Probe, executor: ProbeExecutor) -> ProbeResult:
    try:
        outcome, detail = executor(probe)
    except Exception as error:
        outcome = ProbeOutcome.ERROR
        detail = f"{type(error).__name__}: {error}"

    return ProbeResult(
        probe_id=probe.id,
        outcome=outcome,
        evidence_sha256=hashlib.sha256(detail.encode()).hexdigest(),
        detail=detail,
        trace_id=current_trace_id(),
    )
