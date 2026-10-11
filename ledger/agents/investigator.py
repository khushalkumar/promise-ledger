from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

import neatlogs

from ledger.models import ProbeOutcome, PromiseReport, RootCause, RootCauseBatch


class JsonBackend(Protocol):
    def complete_json(self, system: str, user: str) -> str: ...


SYSTEM_PROMPT = """You are the Promise Ledger Investigator.
Return a RootCause batch as JSON. Group multiple failed probes when one defect explains them.
Every root cause must point to one repository-relative file and give a narrow, testable fix goal.
Do not propose a fix for missing authority, policy conflicts, or migrations that require human
approval.
"""


@neatlogs.span(kind="AGENT", name="violation_investigator")
def investigate_violation(
    report: PromiseReport,
    *,
    target_root: Path,
    backend: JsonBackend,
    entire_context: str,
    git_context: str,
) -> list[RootCause]:
    failed = [
        {
            "probe": probe.model_dump(mode="json"),
            "result": run.effective_result.model_dump(mode="json"),
        }
        for probe, run in zip(report.probes, report.runs, strict=True)
        if run.effective_result.outcome is ProbeOutcome.FAIL
    ]
    request = {
        "target_root": str(target_root),
        "promise": report.promise.model_dump(mode="json"),
        "failed_evidence": failed,
        "entire_context": entire_context,
        "git_context": git_context,
        "schema": RootCauseBatch.model_json_schema(),
    }
    raw = backend.complete_json(SYSTEM_PROMPT, json.dumps(request))
    batch = RootCauseBatch.model_validate(json.loads(raw))
    allowed_probe_ids = {item["probe"]["id"] for item in failed}
    for cause in batch.root_causes:
        if cause.promise_id != report.promise.id:
            raise ValueError(f"root cause {cause.id} names the wrong promise")
        if not cause.probe_ids or not set(cause.probe_ids).issubset(allowed_probe_ids):
            raise ValueError(f"root cause {cause.id} references invalid probes")
        path = Path(cause.file_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"root cause {cause.id} has an unsafe file path")
    return batch.root_causes
