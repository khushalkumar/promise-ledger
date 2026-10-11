from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

import neatlogs

from ledger.models import AgentChange, PullRequestRef, RemediationResult, RootCause


class CodingAgent(Protocol):
    def implement(self, *, worktree: Path, root_cause: RootCause, prompt: str) -> AgentChange: ...


class Workspace(Protocol):
    def prepare(self, branch: str) -> Path: ...

    def changed_files(self, worktree: Path) -> list[str]: ...

    def commit_and_push(self, worktree: Path, *, branch: str, message: str) -> str: ...


class PullRequests(Protocol):
    def find_open(self, branch: str) -> PullRequestRef | None: ...

    def ensure_open(
        self,
        *,
        branch: str,
        title: str,
        body: str,
        commit_sha: str,
        draft: bool,
    ) -> PullRequestRef: ...


class RemediationAgent:
    def __init__(
        self,
        *,
        coding_agent: CodingAgent,
        workspace: Workspace,
        pull_requests: PullRequests,
    ) -> None:
        self.coding_agent = coding_agent
        self.workspace = workspace
        self.pull_requests = pull_requests

    @neatlogs.span(kind="AGENT", name="remediation_agent", capture_input=False)
    def remediate(
        self,
        *,
        run_id: str,
        root_cause: RootCause,
        contract_text: str,
    ) -> RemediationResult:
        branch = _branch_name(root_cause)
        existing = self.pull_requests.find_open(branch)
        if existing is not None:
            return RemediationResult(
                root_cause=root_cause,
                change=None,
                pull_request=existing,
            )
        worktree = self.workspace.prepare(branch)
        prompt = _implementation_prompt(root_cause, contract_text)
        change = self.coding_agent.implement(
            worktree=worktree,
            root_cause=root_cause,
            prompt=prompt,
        )
        actual_changed_files = self.workspace.changed_files(worktree)
        if root_cause.file_path not in actual_changed_files:
            reported = ", ".join(change.changed_files) or "none"
            actual = ", ".join(actual_changed_files) or "none"
            raise ValueError(
                "coding agent did not modify the investigated file "
                f"(reported: {reported}; git: {actual})"
            )
        change = change.model_copy(update={"changed_files": actual_changed_files})
        commit_sha = self.workspace.commit_and_push(
            worktree,
            branch=branch,
            message=f"fix({root_cause.promise_id.lower()}): {root_cause.fix_goal.rstrip('.')}",
        )
        session = change.session_id or "unavailable"
        body = (
            "## Promise Ledger remediation\n\n"
            f"Promise Ledger run: `{run_id}`\n\n"
            f"Root cause: {root_cause.summary}\n\n"
            f"Contract evidence: > {contract_text}\n\n"
            f"Agent result: {change.summary}\n\n"
            f"Verification: {', '.join(change.tests)}\n\n"
            f"Entire session: `{session}`\n"
        )
        pull_request = self.pull_requests.ensure_open(
            branch=branch,
            title=f"{root_cause.promise_id}: {root_cause.fix_goal.rstrip('.')}",
            body=body,
            commit_sha=commit_sha,
            draft=False,
        )
        return RemediationResult(
            root_cause=root_cause,
            change=change,
            pull_request=pull_request,
        )


def _branch_name(root_cause: RootCause) -> str:
    promise = re.sub(r"[^a-z0-9]+", "-", root_cause.promise_id.lower()).strip("-")
    cause = re.sub(r"[^a-z0-9]+", "-", root_cause.id.lower()).strip("-")
    return f"promise-ledger/{promise}-{cause}"[:120].rstrip("-")


def _implementation_prompt(root_cause: RootCause, contract_text: str) -> str:
    return (
        "Implement one narrow contractual remediation in this isolated worktree. "
        "Change only files needed for this root cause, add or update a regression test, "
        "run the repository test and lint commands, and do not commit, push, or open a PR.\n\n"
        f"Promise: {root_cause.promise_id}\n"
        f"Contract: {contract_text}\n"
        f"Root cause: {root_cause.summary}\n"
        f"Required file: {root_cause.file_path}\n"
        f"Fix goal: {root_cause.fix_goal}\n"
    )
