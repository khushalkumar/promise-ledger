import json
import subprocess

from ledger.agents.investigator import EvidenceInvestigator, investigate_violation
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


def test_evidence_investigator_collects_entire_impact_and_git_history(tmp_path):
    outputs = iter(
        [
            json.dumps(
                {
                    "results": [
                        {
                            "symbol_name": "purge_expired_tenants",
                            "file_path": "tasklane/jobs/purge_tenant.py",
                            "start_line": 15,
                            "end_line": 36,
                        }
                    ]
                }
            ),
            json.dumps({"symbol": "purge_expired_tenants", "callers": ["tasklane.purge.main"]}),
            "commit abc123\nAuthor: Khushal Kumar\nfix: add tenant purge\n",
        ]
    )
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=next(outputs), stderr="")

    backend = StubBackend()
    investigator = EvidenceInvestigator(tmp_path, backend, runner=runner)

    causes = investigator.investigate(_violated_report())

    assert len(causes) == 2
    assert commands[0][:3] == ["entire", "graph", "search"]
    assert commands[1][:3] == ["entire", "graph", "impact"]
    assert commands[2][:3] == ["git", "log", "-L"]


def test_evidence_investigator_retries_entire_with_fast_profile(tmp_path):
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        if command[:3] == ["entire", "graph", "search"] and "full" in command:
            raise subprocess.CalledProcessError(1, command, stderr="full profile unavailable")
        if command[:3] == ["entire", "graph", "search"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    {
                        "results": [
                            {
                                "symbol_name": "purge_expired_tenants",
                                "file_path": "tasklane/jobs/purge_tenant.py",
                                "start_line": 15,
                                "end_line": 36,
                            }
                        ]
                    }
                ),
                stderr="",
            )
        if command[:3] == ["entire", "graph", "impact"]:
            return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="commit abc123\n", stderr="")

    investigator = EvidenceInvestigator(tmp_path, StubBackend(), runner=runner)

    causes = investigator.investigate(_violated_report())

    assert causes
    assert commands[0][commands[0].index("--profile") + 1] == "full"
    assert commands[1][commands[1].index("--profile") + 1] == "fast"


def test_evidence_investigator_falls_back_to_grounded_repository_files(tmp_path):
    purge = tmp_path / "tasklane/jobs/purge_tenant.py"
    storage = tmp_path / "infra/storage.tf"
    purge.parent.mkdir(parents=True)
    storage.parent.mkdir(parents=True)
    purge.write_text('PURGE_TABLES = ("comments",)\n')
    storage.write_text("backup_retention_days = 90\n")
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        if command[:2] == ["entire", "graph"]:
            raise subprocess.CalledProcessError(1, command, stderr="graph unavailable")
        return subprocess.CompletedProcess(command, 0, stdout="commit abc123\n", stderr="")

    investigator = EvidenceInvestigator(tmp_path, StubBackend(), runner=runner)

    causes = investigator.investigate(_violated_report())

    assert causes
    assert commands[0][commands[0].index("--profile") + 1] == "full"
    assert commands[1][commands[1].index("--profile") + 1] == "fast"
    assert commands[2][:2] == ["git", "log"]


def test_investigator_canonicalizes_paths_and_merges_duplicate_file_causes(tmp_path):
    class DuplicateBackend:
        def complete_json(self, system: str, user: str) -> str:
            return json.dumps(
                {
                    "root_causes": [
                        {
                            "id": "model-id-one",
                            "promise_id": "P-014",
                            "probe_ids": ["P-014-static-purge"],
                            "category": "source_code",
                            "file_path": "jobs/purge_tenant.py",
                            "summary": "The hard-coded purge list is incomplete.",
                            "fix_goal": "Use complete tenant table coverage.",
                        },
                        {
                            "id": "model-id-two",
                            "promise_id": "P-014",
                            "probe_ids": ["P-014-data-audit_events"],
                            "category": "source_code",
                            "file_path": "purge_tenant.py",
                            "summary": "Expired audit events remain.",
                            "fix_goal": "Delete expired audit events.",
                        },
                    ]
                }
            )

    causes = investigate_violation(
        _violated_report(),
        target_root=tmp_path,
        backend=DuplicateBackend(),
        entire_context="impact",
        git_context="history",
    )

    assert len(causes) == 1
    assert causes[0].id == "rc-p-014-tasklane-jobs-purge-tenant-py"
    assert causes[0].file_path == "tasklane/jobs/purge_tenant.py"
    assert causes[0].probe_ids == [
        "P-014-static-purge",
        "P-014-data-audit_events",
    ]


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
