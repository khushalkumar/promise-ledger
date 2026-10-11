import hashlib
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass

import neatlogs

from ledger.models import Probe, ProbeOutcome, ProbeResult, ProbeRun
from ledger.tracing import current_trace_id


@dataclass(frozen=True)
class ProbeExecution:
    outcome: ProbeOutcome
    detail: str
    evidence_material: bytes

    def __iter__(self):
        yield self.outcome
        yield self.detail

    def __getitem__(self, index: int) -> ProbeOutcome | str:
        return (self.outcome, self.detail)[index]


ProbeExecutor = Callable[[Probe], tuple[ProbeOutcome, str] | ProbeExecution]


@neatlogs.span(kind="TOOL", name="probe_runner")
def run_probe(
    probe: Probe,
    executor: ProbeExecutor,
    *,
    timeout_seconds: float = 30.0,
    max_attempts: int = 2,
) -> ProbeRun:
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")
    primary = _execute(
        probe,
        executor,
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
    )
    fallback = None
    if primary.outcome is ProbeOutcome.ERROR and probe.fallback is not None:
        fallback = _execute(
            probe.fallback,
            executor,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
        )
    return ProbeRun(primary=primary, fallback=fallback)


def _execute(
    probe: Probe,
    executor: ProbeExecutor,
    *,
    timeout_seconds: float,
    max_attempts: int,
) -> ProbeResult:
    for attempt in range(1, max_attempts + 1):
        try:
            execution = _invoke(executor, probe, timeout_seconds)
            if isinstance(execution, ProbeExecution):
                outcome = execution.outcome
                detail = execution.detail
                evidence_material = execution.evidence_material
            else:
                outcome, detail = execution
                evidence_material = detail.encode()
        except Exception as error:
            outcome = ProbeOutcome.ERROR
            detail = f"{type(error).__name__}: {error}"
            evidence_material = detail.encode()
        if outcome is not ProbeOutcome.ERROR or attempt == max_attempts:
            break

    return ProbeResult(
        probe_id=probe.id,
        outcome=outcome,
        evidence_sha256=hashlib.sha256(evidence_material).hexdigest(),
        detail=detail,
        trace_id=current_trace_id(),
    )


def _invoke(executor: ProbeExecutor, probe: Probe, timeout_seconds: float):
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="promise-ledger-probe")
    future = pool.submit(executor, probe)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError as error:
        future.cancel()
        raise TimeoutError(f"probe timed out after {timeout_seconds:g} seconds") from error
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
