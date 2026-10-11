from ledger.models import (
    AgentChange,
    LedgerRun,
    ProbeOutcome,
    PullRequestRef,
    RemediationResult,
    RootCause,
    Verdict,
    WorkflowStage,
)
from ledger.store import RunStore
from ledger.workflow import AutonomousWorkflow
from tests.test_investigator import _violated_report


class StubInvestigator:
    def investigate(self, report):
        assert report.promise.id == "P-014"
        return [
            RootCause(
                id="rc-p014-audit-events",
                promise_id="P-014",
                probe_ids=["P-014-static-purge", "P-014-data-audit_events"],
                category="source_code",
                file_path="tasklane/jobs/purge_tenant.py",
                summary="The purge table list omits audit_events.",
                fix_goal="Delete audit_events in the same tenant purge transaction.",
            ),
            RootCause(
                id="rc-p014-backup-retention",
                promise_id="P-014",
                probe_ids=["P-014-config-backups"],
                category="configuration",
                file_path="infra/storage.tf",
                summary="Backup retention is 90 days.",
                fix_goal="Cap backup retention at 30 days.",
            ),
        ]


class StubRemediator:
    def remediate(self, *, run_id, root_cause, contract_text):
        number = 3 if "audit-events" in root_cause.id else 4
        return RemediationResult(
            root_cause=root_cause,
            change=AgentChange(
                changed_files=[root_cause.file_path],
                summary="fixed",
                tests=["uv run pytest -q"],
                session_id=f"session-{number}",
            ),
            pull_request=PullRequestRef(
                number=number,
                url=f"https://github.com/khushalkumar/tasklane-demo/pull/{number}",
                branch=f"promise-ledger/p-014-fix-{number}",
                commit_sha=f"commit-{number}",
                created=True,
            ),
        )


class StubRechecker:
    def __init__(self):
        self.calls = []

    def recheck(self, *, baseline, affected_probe_ids, commit_shas):
        self.calls.append((affected_probe_ids, commit_shas))
        report = baseline.reports[0].model_copy(update={"verdict": Verdict.HOLDS})
        passing_runs = [
            run.model_copy(
                update={
                    "primary": run.primary.model_copy(update={"outcome": ProbeOutcome.PASS})
                }
            )
            for run in report.runs
        ]
        report = report.model_copy(update={"runs": passing_runs})
        return LedgerRun(reports=[report], conflicts=[])


def test_autonomous_workflow_opens_prs_and_rechecks_only_impacted_probes(tmp_path):
    store = RunStore(f"sqlite:///{tmp_path / 'state.db'}")
    rechecker = StubRechecker()
    workflow = AutonomousWorkflow(
        store=store,
        investigator=StubInvestigator(),
        remediator=StubRemediator(),
        rechecker=rechecker,
    )
    baseline = LedgerRun(reports=[_violated_report()], conflicts=[])

    result = workflow.remediate(
        run_id="run-123",
        target_repository="khushalkumar/tasklane-demo",
        baseline=baseline,
    )

    assert [item.pull_request.number for item in result.remediations] == [3, 4]
    assert result.rechecked.reports[0].verdict is Verdict.HOLDS
    assert rechecker.calls == [
        (
            [
                "P-014-config-backups",
                "P-014-data-audit_events",
                "P-014-static-purge",
            ],
            ["commit-3", "commit-4"],
        )
    ]
    persisted = store.get_run("run-123")
    assert persisted is not None
    assert persisted.stage is WorkflowStage.COMPLETED
    assert [event.stage for event in persisted.events] == [
        WorkflowStage.CREATED,
        WorkflowStage.AUDITING,
        WorkflowStage.INVESTIGATING,
        WorkflowStage.REMEDIATING,
        WorkflowStage.PULL_REQUESTS_OPEN,
        WorkflowStage.RECHECKING,
        WorkflowStage.COMPLETED,
    ]
