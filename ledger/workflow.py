from __future__ import annotations

from typing import Protocol

import neatlogs

from ledger.models import (
    AutonomousRunResult,
    LedgerRun,
    PromiseKind,
    PromiseReport,
    RemediationResult,
    RootCause,
    Verdict,
    WorkflowStage,
)
from ledger.store import RunStore


class Investigator(Protocol):
    def investigate(self, report: PromiseReport) -> list[RootCause]: ...


class Remediator(Protocol):
    def remediate(
        self,
        *,
        run_id: str,
        root_cause: RootCause,
        contract_text: str,
    ) -> RemediationResult: ...


class Rechecker(Protocol):
    def recheck(
        self,
        *,
        baseline: LedgerRun,
        affected_probe_ids: list[str],
        commit_shas: list[str],
    ) -> LedgerRun: ...


SAFE_AUTO_REMEDIATION_KINDS = {PromiseKind.DELETION_DEADLINE}


class AutonomousWorkflow:
    def __init__(
        self,
        *,
        store: RunStore,
        investigator: Investigator,
        remediator: Remediator,
        rechecker: Rechecker,
    ) -> None:
        self.store = store
        self.investigator = investigator
        self.remediator = remediator
        self.rechecker = rechecker

    @neatlogs.span(
        kind="WORKFLOW",
        name="autonomous_remediation",
        capture_input=False,
    )
    def remediate(
        self,
        *,
        run_id: str,
        target_repository: str,
        baseline: LedgerRun,
    ) -> AutonomousRunResult:
        if self.store.get_run(run_id) is None:
            self.store.create_run(run_id, target_repository=target_repository)
        try:
            self.store.record_stage(
                run_id,
                WorkflowStage.AUDITING,
                {"reports": len(baseline.reports)},
            )
            dependencies = {
                probe.id: probe.depends_on
                for report in baseline.reports
                for probe in report.probes
            }
            self.store.replace_probe_dependencies(run_id, dependencies)
            violated = [
                report
                for report in baseline.reports
                if report.verdict is Verdict.VIOLATED
                and report.promise.kind in SAFE_AUTO_REMEDIATION_KINDS
            ]

            self.store.record_stage(
                run_id,
                WorkflowStage.INVESTIGATING,
                {"promise_ids": [report.promise.id for report in violated]},
            )
            root_causes = [
                cause
                for report in violated
                for cause in self.investigator.investigate(report)
            ]

            self.store.record_stage(
                run_id,
                WorkflowStage.REMEDIATING,
                {"root_cause_ids": [cause.id for cause in root_causes]},
            )
            reports = {report.promise.id: report for report in baseline.reports}
            remediations = [
                self.remediator.remediate(
                    run_id=run_id,
                    root_cause=cause,
                    contract_text=reports[cause.promise_id].promise.source.text,
                )
                for cause in root_causes
            ]

            self.store.record_stage(
                run_id,
                WorkflowStage.PULL_REQUESTS_OPEN,
                {
                    "pull_requests": [
                        remediation.pull_request.url for remediation in remediations
                    ]
                },
            )
            changed_dependencies = sorted({cause.file_path for cause in root_causes})
            affected_probe_ids = sorted(
                {
                    *self.store.affected_probe_ids(run_id, changed_dependencies),
                    *(probe_id for cause in root_causes for probe_id in cause.probe_ids),
                }
            )
            commit_shas = [item.pull_request.commit_sha for item in remediations]

            self.store.record_stage(
                run_id,
                WorkflowStage.RECHECKING,
                {"probe_ids": affected_probe_ids, "commit_shas": commit_shas},
            )
            rechecked = self.rechecker.recheck(
                baseline=baseline,
                affected_probe_ids=affected_probe_ids,
                commit_shas=commit_shas,
            )
            self.store.record_stage(
                run_id,
                WorkflowStage.COMPLETED,
                {
                    "verdicts": {
                        report.promise.id: report.verdict.value for report in rechecked.reports
                    }
                },
            )
            return AutonomousRunResult(
                run_id=run_id,
                baseline=baseline,
                root_causes=root_causes,
                remediations=remediations,
                rechecked=rechecked,
            )
        except Exception as error:
            self.store.record_stage(
                run_id,
                WorkflowStage.FAILED,
                {"error": f"{type(error).__name__}: {error}"},
            )
            raise
