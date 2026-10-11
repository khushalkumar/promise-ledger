from ledger.models import Probe, ProbeKind, ProbeOutcome
from ledger.probes import runner
from ledger.probes.runner import ProbeExecution, run_probe


def probe(*, fallback: Probe | None = None) -> Probe:
    return Probe(
        id="P-017-cloud",
        kind=ProbeKind.CONFIG,
        template="cloud.backup_retention",
        params={"maximum_days": 30},
        depends_on=["aws:tasklane-backups"],
        fallback=fallback,
    )


def terraform_fallback() -> Probe:
    return Probe(
        id="P-017-terraform",
        kind=ProbeKind.CONFIG,
        template="terraform.backup_retention",
        params={"maximum_days": 30},
        depends_on=["infra/storage.tf"],
    )


def test_error_runs_fallback_and_uses_its_pass_result():
    calls = []

    def executor(current: Probe):
        calls.append(current.id)
        if current.id == "P-017-cloud":
            raise PermissionError("AccessDenied")
        return ProbeOutcome.PASS, "Terraform expiration is 30 days"

    execution = run_probe(probe(fallback=terraform_fallback()), executor)

    assert calls == ["P-017-cloud", "P-017-cloud", "P-017-terraform"]
    assert execution.primary.outcome is ProbeOutcome.ERROR
    assert execution.primary.detail == "PermissionError: AccessDenied"
    assert execution.fallback is not None
    assert execution.effective_result.outcome is ProbeOutcome.PASS


def test_failure_does_not_run_fallback():
    calls = []

    def executor(current: Probe):
        calls.append(current.id)
        return ProbeOutcome.FAIL, "retention is 90 days"

    execution = run_probe(probe(fallback=terraform_fallback()), executor)

    assert calls == ["P-017-cloud"]
    assert execution.fallback is None
    assert execution.effective_result.outcome is ProbeOutcome.FAIL


def test_evidence_hash_is_deterministic():
    def executor(current: Probe):
        return ProbeOutcome.PASS, "stable evidence"

    first = run_probe(probe(), executor)
    second = run_probe(probe(), executor)

    assert first.primary.evidence_sha256 == second.primary.evidence_sha256
    assert len(first.primary.evidence_sha256) == 64


def test_evidence_hash_tracks_the_underlying_artifact_not_only_display_detail():
    first = run_probe(
        probe(),
        lambda current: ProbeExecution(
            outcome=ProbeOutcome.PASS,
            detail="stable evidence",
            evidence_material=b"artifact revision one",
        ),
    )
    second = run_probe(
        probe(),
        lambda current: ProbeExecution(
            outcome=ProbeOutcome.PASS,
            detail="stable evidence",
            evidence_material=b"artifact revision two",
        ),
    )

    assert first.primary.evidence_sha256 != second.primary.evidence_sha256


def test_transient_probe_error_is_retried_before_fallback():
    calls = 0

    def executor(current: Probe):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionError("temporary database interruption")
        return ProbeOutcome.PASS, "query recovered"

    execution = run_probe(probe(fallback=terraform_fallback()), executor)

    assert calls == 2
    assert execution.primary.outcome is ProbeOutcome.PASS
    assert execution.fallback is None


def test_probe_timeout_becomes_error_and_uses_fallback():
    import time

    def executor(current: Probe):
        if current.id == "P-017-cloud":
            time.sleep(0.05)
        return ProbeOutcome.PASS, "fallback evidence"

    execution = run_probe(
        probe(fallback=terraform_fallback()),
        executor,
        timeout_seconds=0.001,
    )

    assert execution.primary.outcome is ProbeOutcome.ERROR
    assert "timed out" in execution.primary.detail
    assert execution.fallback is not None
    assert execution.fallback.outcome is ProbeOutcome.PASS


def test_probe_evidence_keeps_the_active_neatlogs_trace_id(monkeypatch):
    trace_id = "0123456789abcdef0123456789abcdef"
    monkeypatch.setattr(runner, "current_trace_id", lambda: trace_id)

    execution = run_probe(
        probe(fallback=terraform_fallback()),
        lambda current: (
            (ProbeOutcome.ERROR, "AccessDenied")
            if current.id == "P-017-cloud"
            else (ProbeOutcome.PASS, "Terraform expiration is 30 days")
        ),
    )

    assert execution.primary.trace_id == trace_id
    assert execution.fallback is not None
    assert execution.fallback.trace_id == trace_id
