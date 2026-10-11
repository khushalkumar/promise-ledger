from pathlib import Path

from ledger.agents.remediator import RemediationAgent
from ledger.models import AgentChange, PullRequestRef, RootCause


class StubCodingAgent:
    def implement(self, *, worktree: Path, root_cause: RootCause, prompt: str) -> AgentChange:
        assert root_cause.fix_goal in prompt
        return AgentChange(
            changed_files=[root_cause.file_path],
            summary=f"Implemented {root_cause.id}",
            tests=["uv run pytest -q"],
            session_id="entire-session-123",
        )


class StubWorkspace:
    def __init__(self, root: Path):
        self.root = root
        self.branches = []

    def prepare(self, branch: str) -> Path:
        self.branches.append(branch)
        return self.root

    def changed_files(self, worktree: Path) -> list[str]:
        return ["tasklane/jobs/purge_tenant.py"]

    def commit_and_push(self, worktree: Path, *, branch: str, message: str) -> str:
        return "abc123"


class StubPullRequests:
    def __init__(self, existing: PullRequestRef | None = None):
        self.requests = []
        self.existing = existing

    def find_open(self, branch: str) -> PullRequestRef | None:
        return self.existing

    def ensure_open(self, **request) -> PullRequestRef:
        self.requests.append(request)
        return PullRequestRef(
            number=3,
            url="https://github.com/khushalkumar/tasklane-demo/pull/3",
            branch=request["branch"],
            commit_sha=request["commit_sha"],
            created=True,
        )


def test_remediator_runs_agent_and_opens_normal_idempotent_pull_request(tmp_path):
    workspace = StubWorkspace(tmp_path)
    pull_requests = StubPullRequests()
    agent = RemediationAgent(
        coding_agent=StubCodingAgent(),
        workspace=workspace,
        pull_requests=pull_requests,
    )
    cause = RootCause(
        id="rc-p014-audit-events",
        promise_id="P-014",
        probe_ids=["P-014-static-purge", "P-014-data-audit_events"],
        category="source_code",
        file_path="tasklane/jobs/purge_tenant.py",
        line_start=13,
        summary="The purge table list omits audit_events.",
        fix_goal="Delete audit_events in the same tenant purge transaction.",
    )

    result = agent.remediate(
        run_id="run-123",
        root_cause=cause,
        contract_text="Delete customer data within 30 days.",
    )

    assert result.pull_request.created is True
    assert result.pull_request.number == 3
    assert workspace.branches == ["promise-ledger/p-014-rc-p014-audit-events"]
    request = pull_requests.requests[0]
    assert request["draft"] is False
    assert "Promise Ledger run: `run-123`" in request["body"]
    assert "Entire session: `entire-session-123`" in request["body"]
    assert request["commit_sha"] == "abc123"


def test_remediator_uses_git_changes_instead_of_model_reported_paths(tmp_path):
    class EmptyReportingCodingAgent(StubCodingAgent):
        def implement(self, **kwargs) -> AgentChange:
            change = super().implement(**kwargs)
            return change.model_copy(update={"changed_files": []})

    workspace = StubWorkspace(tmp_path)
    pull_requests = StubPullRequests()
    agent = RemediationAgent(
        coding_agent=EmptyReportingCodingAgent(),
        workspace=workspace,
        pull_requests=pull_requests,
    )
    cause = RootCause(
        id="rc-p014-audit-events",
        promise_id="P-014",
        probe_ids=["P-014-static-purge"],
        category="source_code",
        file_path="tasklane/jobs/purge_tenant.py",
        summary="The purge table list omits audit_events.",
        fix_goal="Delete audit_events in the same tenant purge transaction.",
    )

    result = agent.remediate(
        run_id="run-123",
        root_cause=cause,
        contract_text="Delete customer data within 30 days.",
    )

    assert result.change is not None
    assert result.change.changed_files == ["tasklane/jobs/purge_tenant.py"]


def test_remediator_reuses_existing_open_pull_request_without_running_agent(tmp_path):
    existing = PullRequestRef(
        number=3,
        url="https://github.com/khushalkumar/tasklane-demo/pull/3",
        branch="promise-ledger/p-014-rc-p014-audit-events",
        commit_sha="abc123",
        created=False,
    )
    coding_agent = StubCodingAgent()
    workspace = StubWorkspace(tmp_path)
    pull_requests = StubPullRequests(existing)
    agent = RemediationAgent(
        coding_agent=coding_agent,
        workspace=workspace,
        pull_requests=pull_requests,
    )
    cause = RootCause(
        id="rc-p014-audit-events",
        promise_id="P-014",
        probe_ids=["P-014-static-purge"],
        category="source_code",
        file_path="tasklane/jobs/purge_tenant.py",
        summary="The purge table list omits audit_events.",
        fix_goal="Delete audit_events in the same tenant purge transaction.",
    )

    result = agent.remediate(
        run_id="run-456",
        root_cause=cause,
        contract_text="Delete customer data within 30 days.",
    )

    assert result.pull_request == existing
    assert result.change is None
    assert workspace.branches == []
    assert pull_requests.requests == []
