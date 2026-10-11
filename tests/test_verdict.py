import pytest

from ledger.models import ProbeOutcome, ProbeResult, Verdict
from ledger.verdict import evaluate_verdict


def result(outcome: ProbeOutcome, probe_id: str = "probe-1") -> ProbeResult:
    return ProbeResult(
        probe_id=probe_id,
        outcome=outcome,
        evidence_sha256="0" * 64,
        detail=f"probe returned {outcome}",
    )


@pytest.mark.parametrize(
    ("results", "expected"),
    [
        ([], Verdict.UNVERIFIABLE),
        ([result(ProbeOutcome.PASS)], Verdict.HOLDS),
        ([result(ProbeOutcome.ERROR)], Verdict.AT_RISK),
        ([result(ProbeOutcome.FAIL)], Verdict.VIOLATED),
        (
            [result(ProbeOutcome.PASS), result(ProbeOutcome.ERROR, "probe-2")],
            Verdict.AT_RISK,
        ),
        (
            [result(ProbeOutcome.ERROR), result(ProbeOutcome.FAIL, "probe-2")],
            Verdict.VIOLATED,
        ),
    ],
)
def test_verdict_precedence(results, expected):
    assert evaluate_verdict(results) is expected

