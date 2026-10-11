from ledger.models import Probe, ProbeKind, ProbeOutcome
from ledger.probes.runner import run_probe


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

    assert calls == ["P-017-cloud", "P-017-terraform"]
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

