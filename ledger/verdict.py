from collections.abc import Sequence

from ledger.models import ProbeOutcome, ProbeResult, Verdict


def evaluate_verdict(results: Sequence[ProbeResult]) -> Verdict:
    if not results:
        return Verdict.UNVERIFIABLE

    outcomes = {result.outcome for result in results}
    if ProbeOutcome.FAIL in outcomes:
        return Verdict.VIOLATED
    if ProbeOutcome.ERROR in outcomes:
        return Verdict.AT_RISK
    return Verdict.HOLDS
