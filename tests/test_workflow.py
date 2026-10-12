from ledger.models import (
    AgentChange,
    LedgerRun,
    ProbeOutcome,
    PromiseKind,
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


def test_autonomous_workflow_rechecks_every_probe_for_remediated_promise(tmp_path):
    class IncompleteInvestigator(StubInvestigator):
        def investigate(self, report):
            causes = super().investigate(report)
            causes[0] = causes[0].model_copy(
                update={"probe_ids": ["P-014-static-purge"]}
            )
            return causes

    store = RunStore(f"sqlite:///{tmp_path / 'state.db'}")
    rechecker = StubRechecker()
    workflow = AutonomousWorkflow(
        store=store,
        investigator=IncompleteInvestigator(),
        remediator=StubRemediator(),
        rechecker=rechecker,
    )

    workflow.remediate(
        run_id="run-123",
        target_repository="khushalkumar/tasklane-demo",
        baseline=LedgerRun(reports=[_violated_report()], conflicts=[]),
    )

    assert rechecker.calls[0][0] == [
        "P-014-config-backups",
        "P-014-data-audit_events",
        "P-014-static-purge",
    ]


def test_autonomous_workflow_never_auto_remediates_data_residency(tmp_path):
    deletion = _violated_report()
    residency = deletion.model_copy(
        update={
            "promise": deletion.promise.model_copy(
                update={"id": "P-021", "kind": PromiseKind.DATA_RESIDENCY}
            )
        }
    )
    investigated = []

    class RecordingInvestigator:
        def investigate(self, report):
            investigated.append(report.promise.id)
            return []

    class NoopRechecker:
        def recheck(self, *, baseline, affected_probe_ids, commit_shas):
            return baseline

    workflow = AutonomousWorkflow(
        store=RunStore(f"sqlite:///{tmp_path / 'state.db'}"),
        investigator=RecordingInvestigator(),
        remediator=StubRemediator(),
        rechecker=NoopRechecker(),
    )

    workflow.remediate(
        run_id="run-safe-policy",
        target_repository="khushalkumar/tasklane-demo",
        baseline=LedgerRun(reports=[deletion, residency]),
    )

    assert investigated == ["P-014"]


def test_autonomous_workflow_prefers_stricter_overlapping_remediation(tmp_path):
    thirty_day = _violated_report()
    fifteen_day = thirty_day.model_copy(
        update={
            "promise": thirty_day.promise.model_copy(
                update={"id": "P-045", "deadline_days": 15}
            ),
            "probes": [
                probe.model_copy(update={"id": probe.id.replace("P-014", "P-045")})
                for probe in thirty_day.probes
            ],
            "runs": [
                run.model_copy(
                    update={
                        "primary": run.primary.model_copy(
                            update={
                                "probe_id": run.primary.probe_id.replace("P-014", "P-045")
                            }
                        )
                    }
                )
                for run in thirty_day.runs
            ],
        }
    )
    remediated = []
    rechecks = []

    class OverlappingInvestigator:
        def investigate(self, report):
            promise_id = report.promise.id
            return [
                RootCause(
                    id=f"rc-{promise_id.lower()}-purge",
                    promise_id=promise_id,
                    probe_ids=[f"{promise_id}-static-purge"],
                    category="source_code",
                    file_path="tasklane/jobs/purge_tenant.py",
                    summary="Purge cutoff is too long.",
                    fix_goal=f"Enforce the {report.promise.deadline_days}-day cutoff.",
                )
            ]

    class RecordingRemediator:
        def remediate(self, *, run_id, root_cause, contract_text):
            remediated.append(root_cause.promise_id)
            return RemediationResult(
                root_cause=root_cause,
                change=None,
                pull_request=PullRequestRef(
                    number=45,
                    url="https://github.com/khushalkumar/tasklane-demo/pull/45",
                    branch="promise-ledger/p-045-purge",
                    commit_sha="commit-p-045",
                    created=True,
                ),
            )

    class RecordingRechecker:
        def recheck(self, *, baseline, affected_probe_ids, commit_shas):
            rechecks.append((affected_probe_ids, commit_shas))
            return baseline

    workflow = AutonomousWorkflow(
        store=RunStore(f"sqlite:///{tmp_path / 'state.db'}"),
        investigator=OverlappingInvestigator(),
        remediator=RecordingRemediator(),
        rechecker=RecordingRechecker(),
    )

    workflow.remediate(
        run_id="run-overlap",
        target_repository="khushalkumar/tasklane-demo",
        baseline=LedgerRun(reports=[thirty_day, fifteen_day], conflicts=[]),
    )

    assert remediated == ["P-045"]
    assert rechecks == [
        (
            [
                "P-014-config-backups",
                "P-014-data-audit_events",
                "P-014-static-purge",
                "P-045-config-backups",
                "P-045-data-audit_events",
                "P-045-static-purge",
            ],
            ["commit-p-045"],
        )
    ]
