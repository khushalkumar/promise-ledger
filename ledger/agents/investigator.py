from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
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

Runner = Callable[..., subprocess.CompletedProcess[str]]


class EvidenceInvestigator:
    def __init__(
        self,
        target_root: Path,
        backend: JsonBackend,
        *,
        runner: Runner = subprocess.run,
    ) -> None:
        self.target_root = target_root.resolve()
        self.backend = backend
        self.runner = runner

    def investigate(self, report: PromiseReport) -> list[RootCause]:
        query = " ".join(
            run.effective_result.detail
            for run in report.runs
            if run.effective_result.outcome is ProbeOutcome.FAIL
        )[:1000]
        search = self._run(
            [
                "entire",
                "graph",
                "search",
                "--repo",
                str(self.target_root),
                "--profile",
                "full",
                "--format",
                "json",
                "--top-k",
                "5",
                "--query",
                query,
            ]
        )
        results = json.loads(search.stdout).get("results", [])
        if not results:
            raise ValueError("Entire Graph returned no evidence for the violation")
        top = results[0]
        symbol = str(top.get("symbol_name") or f"{top['file_path']}:{top['start_line']}")
        impact = self._run(
            [
                "entire",
                "graph",
                "impact",
                "--repo",
                str(self.target_root),
                "--symbol",
                symbol,
                "--profile",
                "full",
                "--format",
                "json",
            ]
        )
        line_range = f"{top['start_line']},{top['end_line']}:{top['file_path']}"
        history = self._run(
            [
                "git",
                "log",
                "-L",
                line_range,
                "--format=commit %H%nAuthor: %an <%ae>%n%s",
                "-n",
                "5",
            ]
        )
        return investigate_violation(
            report,
            target_root=self.target_root,
            backend=self.backend,
            entire_context=impact.stdout[:20_000],
            git_context=history.stdout[:20_000],
        )

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        return self.runner(
            command,
            cwd=self.target_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )


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
    return _canonicalize_and_merge(batch.root_causes, failed)


def _canonicalize_and_merge(
    causes: list[RootCause], failed: list[dict[str, object]]
) -> list[RootCause]:
    allowed_paths = sorted(
        {
            path
            for item in failed
            if isinstance(item.get("probe"), dict)
            for path in [item["probe"].get("params", {}).get("path")]
            if isinstance(path, str)
        }
    )
    probe_order = {
        item["probe"]["id"]: index
        for index, item in enumerate(failed)
        if isinstance(item.get("probe"), dict)
    }
    grouped: dict[tuple[str, str], list[RootCause]] = {}
    for cause in causes:
        canonical_path = _canonical_path(cause, allowed_paths)
        canonical = cause.model_copy(update={"file_path": canonical_path})
        grouped.setdefault((canonical.promise_id, canonical_path), []).append(canonical)

    merged = []
    for (promise_id, file_path), file_causes in grouped.items():
        probe_ids = sorted(
            {probe_id for cause in file_causes for probe_id in cause.probe_ids},
            key=lambda probe_id: probe_order.get(probe_id, len(probe_order)),
        )
        summaries = list(dict.fromkeys(cause.summary for cause in file_causes))
        goals = list(dict.fromkeys(cause.fix_goal for cause in file_causes))
        line_starts = [cause.line_start for cause in file_causes if cause.line_start is not None]
        slug = re.sub(r"[^a-z0-9]+", "-", file_path.lower()).strip("-")
        merged.append(
            RootCause(
                id=f"rc-{promise_id.lower()}-{slug}"[:120].rstrip("-"),
                promise_id=promise_id,
                probe_ids=probe_ids,
                category=file_causes[0].category,
                file_path=file_path,
                line_start=min(line_starts) if line_starts else None,
                summary=" ".join(summaries),
                fix_goal=" ".join(goals),
            )
        )
    return merged


def _canonical_path(cause: RootCause, allowed_paths: list[str]) -> str:
    if cause.file_path in allowed_paths:
        return cause.file_path
    candidate = Path(cause.file_path)
    matches = [
        path
        for path in allowed_paths
        if path.endswith(f"/{cause.file_path}") or Path(path).name == candidate.name
    ]
    if len(matches) != 1:
        raise ValueError(f"root cause {cause.id} does not name a grounded repository file")
    return matches[0]
