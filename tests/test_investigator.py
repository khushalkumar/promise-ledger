import json

from ledger.agents.investigator import investigate_violation
from ledger.models import (
    Probe,
    ProbeKind,
    ProbeOutcome,
    ProbeResult,
    ProbeRun,
    Promise,
    PromiseKind,
    PromiseReport,
    SourceSpan,
    Verdict,
)


class StubBackend:
    def complete_json(self, system: str, user: str) -> str:
        assert "RootCause" in system
        assert "purge omits tenant table" in user
        return json.dumps(
            {
                "root_causes": [
                    {
                        "id": "rc-p014-audit-events",
                        "promise_id": "P-014",
                        "probe_ids": ["P-014-static-purge", "P-014-data-audit_events"],
                        "category": "source_code",
                        "file_path": "tasklane/jobs/purge_tenant.py",
                        "line_start": 13,
                        "summary": "The purge table list omits audit_events.",
                        "fix_goal": "Delete audit_events in the same tenant purge transaction.",
                    },
                    {
                        "id": "rc-p014-backup-retention",
                        "promise_id": "P-014",
                        "probe_ids": ["P-014-config-backups"],
                        "category": "configuration",
                        "file_path": "infra/storage.tf",
                        "line_start": 8,
                        "summary": "Backup expiry is configured for 90 days.",
                        "fix_goal": "Cap backup expiry at 30 days.",
                    },
                ]
            }
        )


def test_investigator_turns_failed_evidence_into_two_actionable_root_causes(tmp_path):
    report = _violated_report()

    result = investigate_violation(
        report,
        target_root=tmp_path,
        backend=StubBackend(),
        entire_context="impact: purge_expired_tenants -> audit_events",
        git_context="commit abc123 planted purge table list",
    )

    assert [cause.file_path for cause in result] == [
        "tasklane/jobs/purge_tenant.py",
        "infra/storage.tf",
    ]
    assert result[0].probe_ids == ["P-014-static-purge", "P-014-data-audit_events"]
    assert result[1].fix_goal == "Cap backup expiry at 30 days."


def _violated_report() -> PromiseReport:
    promise = Promise(
        id="P-014",
        kind=PromiseKind.DELETION_DEADLINE,
        actor="Tasklane",
        object="customer personal data",
        includes=["backups"],
        trigger="contract.terminated",
        deadline_days=30,
        source=SourceSpan(
            document="Northwind_DPA_v3.pdf",
            clause="7.2",
            text="Delete customer data and backups within 30 days.",
        ),
    )
    probes = [
        Probe(
            id="P-014-static-purge",
            kind=ProbeKind.STATIC,
            template="static.purge_covers_tables",
            params={"path": "tasklane/jobs/purge_tenant.py"},
            depends_on=["tasklane/jobs/purge_tenant.py", "audit_events"],
        ),
        Probe(
            id="P-014-data-audit_events",
            kind=ProbeKind.DATA,
            template="sql.no_rows_after_deadline",
            params={"table": "audit_events"},
            depends_on=["audit_events", "tenants"],
        ),
        Probe(
            id="P-014-config-backups",
            kind=ProbeKind.CONFIG,
            template="terraform.maximum_retention",
            params={"path": "infra/storage.tf", "maximum_days": 30},
            depends_on=["infra/storage.tf"],
        ),
    ]
    details = [
        "purge omits tenant table(s): audit_events",
        "audit_events has 1284 row(s) past the 30-day deadline",
        "configured retention is 90 days; contract maximum is 30",
    ]
    runs = [
        ProbeRun(
            primary=ProbeResult(
                probe_id=probe.id,
                outcome=ProbeOutcome.FAIL,
                evidence_sha256=f"hash-{index}",
                detail=detail,
            )
        )
        for index, (probe, detail) in enumerate(zip(probes, details, strict=True))
    ]
    return PromiseReport(promise=promise, probes=probes, runs=runs, verdict=Verdict.VIOLATED)
