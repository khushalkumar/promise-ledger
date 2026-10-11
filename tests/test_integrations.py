import json
import subprocess
from pathlib import Path

import pytest

from ledger.integrations.codex import AgentChangeOutput, CodexCodingAgent
from ledger.integrations.github import GhPullRequests
from ledger.integrations.workspace import GitWorkspace
from ledger.models import RootCause


class RecordingRunner:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.commands = []

    def __call__(self, command, **kwargs):
        self.commands.append((command, kwargs))
        output = next(self.outputs)
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")


def test_codex_output_schema_is_strict_for_responses_api():
    schema = AgentChangeOutput.model_json_schema()

    assert schema["additionalProperties"] is False


def test_gh_pull_requests_reuses_open_branch_without_creating_duplicate():
    runner = RecordingRunner(
        [
            json.dumps(
                [
                    {
                        "number": 3,
                        "url": "https://github.com/khushalkumar/tasklane-demo/pull/3",
                        "headRefName": "promise-ledger/p-014-rc-p014-audit-events",
                        "headRefOid": "abc123",
                    }
                ]
            )
        ]
    )
    client = GhPullRequests("khushalkumar/tasklane-demo", runner=runner)

    result = client.find_open("promise-ledger/p-014-rc-p014-audit-events")

    assert result is not None
    assert result.number == 3
    assert result.created is False
    assert len(runner.commands) == 1
    assert runner.commands[0][0][:3] == ["gh", "pr", "list"]


def test_gh_pull_requests_creates_normal_pr_with_body_file(tmp_path):
    runner = RecordingRunner(
        [
            json.dumps([]),
            "https://github.com/khushalkumar/tasklane-demo/pull/3\n",
            json.dumps(
                {
                    "number": 3,
                    "url": "https://github.com/khushalkumar/tasklane-demo/pull/3",
                    "headRefName": "promise-ledger/p-014-rc-p014-audit-events",
                    "headRefOid": "abc123",
                }
            ),
        ]
    )
    client = GhPullRequests("khushalkumar/tasklane-demo", runner=runner)

    result = client.ensure_open(
        branch="promise-ledger/p-014-rc-p014-audit-events",
        title="P-014: purge audit events",
        body="body with `literal` shell characters",
        commit_sha="abc123",
        draft=False,
    )

    assert result.created is True
    create_command, create_kwargs = runner.commands[1]
    assert "--draft" not in create_command
    body_path = create_command[create_command.index("--body-file") + 1]
    assert body_path not in create_kwargs.get("input", "")


def test_git_workspace_creates_isolated_branch_commits_and_pushes(tmp_path):
    source = tmp_path / "source"
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "init", "-b", "main", str(source)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(source), "config", "user.name", "Khushal Kumar"], check=True)
    subprocess.run(
        ["git", "-C", str(source), "config", "user.email", "kkhushal1531@gmail.com"],
        check=True,
    )
    (source / "app.py").write_text("VALUE = 1\n")
    subprocess.run(["git", "-C", str(source), "add", "app.py"], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-m", "initial"], check=True)
    subprocess.run(["git", "-C", str(source), "remote", "add", "origin", str(remote)], check=True)
    subprocess.run(["git", "-C", str(source), "push", "-u", "origin", "main"], check=True)
    workspace = GitWorkspace(source, tmp_path / "worktrees")

    worktree = workspace.prepare("promise-ledger/p-014-fix")
    (worktree / "app.py").write_text("VALUE = 2\n")
    commit_sha = workspace.commit_and_push(
        worktree,
        branch="promise-ledger/p-014-fix",
        message="fix(p-014): update value",
    )

    assert workspace.changed_files(worktree) == []
    remote_value = subprocess.run(
        ["git", "--git-dir", str(remote), "show", f"{commit_sha}:app.py"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert remote_value == "VALUE = 2\n"


def test_codex_coding_agent_runs_headless_with_schema_and_captures_session(tmp_path):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / "app.py").write_text("VALUE = 1\n")

    def runner(command, **kwargs):
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text(
            json.dumps(
                {
                    "summary": "Updated the value and added a regression test.",
                    "changed_files": ["app.py", "tests/test_app.py"],
                    "tests": ["uv run pytest -q"],
                }
            )
        )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"type": "thread.started", "thread_id": "thread-123"}) + "\n",
            stderr="",
        )

    agent = CodexCodingAgent(binary="codex", runner=runner)
    cause = RootCause(
        id="rc-p014-audit-events",
        promise_id="P-014",
        probe_ids=["P-014-static-purge"],
        category="source_code",
        file_path="app.py",
        summary="The value is wrong.",
        fix_goal="Set the value to two.",
    )

    result = agent.implement(worktree=worktree, root_cause=cause, prompt="Fix it safely")

    assert result.session_id == "thread-123"
    assert result.changed_files == ["app.py", "tests/test_app.py"]
    assert result.tests == ["uv run pytest -q"]


def test_codex_coding_agent_bypasses_pretrusted_hooks_for_automation(tmp_path):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text(
            json.dumps({"summary": "fixed", "changed_files": ["app.py"], "tests": []})
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    agent = CodexCodingAgent(binary="codex", runner=runner)
    cause = RootCause(
        id="rc-1",
        promise_id="P-014",
        probe_ids=["probe-1"],
        category="source_code",
        file_path="app.py",
        summary="Bug.",
        fix_goal="Fix bug.",
    )

    agent.implement(worktree=worktree, root_cause=cause, prompt="Fix it")

    assert "--dangerously-bypass-hook-trust" in commands[0]
    assert "--approve-for-me" in commands[0]
    assert "--sandbox" not in commands[0]
    assert not any("mcp_servers." in part for part in commands[0])


def test_codex_coding_agent_uses_azure_responses_provider_from_environment(
    tmp_path, monkeypatch
):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text(
            json.dumps({"summary": "fixed", "changed_files": ["app.py"], "tests": []})
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setenv("PROMISE_LEDGER_AZURE_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("PROMISE_LEDGER_AZURE_API_KEY", "secret-not-in-command")
    monkeypatch.setenv("PROMISE_LEDGER_AZURE_DEPLOYMENT", "gpt-5.6-sol")
    monkeypatch.setenv("PROMISE_LEDGER_AZURE_REASONING_EFFORT", "high")
    agent = CodexCodingAgent(binary="codex", runner=runner)
    cause = RootCause(
        id="rc-1",
        promise_id="P-014",
        probe_ids=["probe-1"],
        category="source_code",
        file_path="app.py",
        summary="Bug.",
        fix_goal="Fix bug.",
    )

    agent.implement(worktree=worktree, root_cause=cause, prompt="Fix it")

    command = commands[0]
    assert command[command.index("--model") + 1] == "gpt-5.6-sol"
    assert "--ignore-user-config" in command
    assert 'model_provider="promise_ledger_azure"' in command
    assert 'model_reasoning_effort="high"' in command
    assert (
        'model_providers.promise_ledger_azure.base_url="https://example.openai.azure.com/openai/v1"'
        in command
    )
    assert (
        'model_providers.promise_ledger_azure.env_http_headers={"api-key" = '
        '"PROMISE_LEDGER_AZURE_API_KEY"}' in command
    )
    assert 'model_providers.promise_ledger_azure.wire_api="responses"' in command
    assert "secret-not-in-command" not in " ".join(command)


def test_codex_coding_agent_bypasses_inner_sandbox_only_when_externally_isolated(
    tmp_path, monkeypatch
):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text(
            json.dumps({"summary": "fixed", "changed_files": ["app.py"], "tests": []})
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setenv("PROMISE_LEDGER_CODEX_EXTERNAL_SANDBOX", "true")
    agent = CodexCodingAgent(binary="codex", runner=runner)
    cause = RootCause(
        id="rc-1",
        promise_id="P-014",
        probe_ids=["probe-1"],
        category="source_code",
        file_path="app.py",
        summary="Bug.",
        fix_goal="Fix bug.",
    )

    agent.implement(worktree=worktree, root_cause=cause, prompt="Fix it")

    assert "--dangerously-bypass-approvals-and-sandbox" in commands[0]
    assert "--approve-for-me" not in commands[0]


def test_codex_coding_agent_rejects_non_sol_azure_deployment(monkeypatch):
    monkeypatch.setenv("PROMISE_LEDGER_AZURE_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("PROMISE_LEDGER_AZURE_API_KEY", "secret")
    monkeypatch.setenv("PROMISE_LEDGER_AZURE_DEPLOYMENT", "gpt-4.1")

    with pytest.raises(ValueError, match="GPT-5.6 Sol"):
        CodexCodingAgent(binary="codex").implement(
            worktree=Path("/tmp/worktree"),
            root_cause=RootCause(
                id="rc-1",
                promise_id="P-014",
                probe_ids=["probe-1"],
                category="source_code",
                file_path="app.py",
                summary="Bug.",
                fix_goal="Fix bug.",
            ),
            prompt="Fix it",
        )


def test_codex_coding_agent_surfaces_cli_failure_without_command_dump(tmp_path):
    worktree = tmp_path / "worktree"
    worktree.mkdir()

    def runner(command, **kwargs):
        raise subprocess.CalledProcessError(
            2,
            command,
            output='{"type":"error","message":"Agent startup failed"}',
            stderr="Hooks need review",
        )

    agent = CodexCodingAgent(binary="codex", runner=runner)
    cause = RootCause(
        id="rc-1",
        promise_id="P-014",
        probe_ids=["probe-1"],
        category="source_code",
        file_path="app.py",
        summary="Bug.",
        fix_goal="Fix bug.",
    )

    with pytest.raises(RuntimeError, match="(?s)Agent startup failed.*Hooks need review"):
        agent.implement(worktree=worktree, root_cause=cause, prompt="Fix it")
