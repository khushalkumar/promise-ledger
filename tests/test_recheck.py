import sqlite3
import subprocess
from pathlib import Path

import pytest

from ledger import orchestrator
from ledger.integrations.recheck import ConfiguredRechecker
from ledger.models import PromiseKind, Verdict
from ledger.orchestrator import recheck_ledger, run_ledger
from tests.test_orchestrator import demo_context, promise


def test_rechecker_merge_uses_explicit_khushal_identity(tmp_path):
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    rechecker = ConfiguredRechecker(
        source_repository=tmp_path,
        worktree_root=tmp_path / "worktrees",
        runner=runner,
    )

    rechecker._merge_head("abc123", Path(tmp_path))

    assert commands == [
        [
            "git",
            "-c",
            "user.name=Khushal Kumar",
            "-c",
            "user.email=kkhushal1531@gmail.com",
            "merge",
            "--no-ff",
            "--no-edit",
            "abc123",
        ]
    ]


def test_rechecker_fetches_each_pr_commit_before_cherry_pick(tmp_path):
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    rechecker = ConfiguredRechecker(
        source_repository=tmp_path,
        worktree_root=tmp_path / "worktrees",
        runner=runner,
    )

    commit_sha = "a" * 40
    rechecker._fetch_commit(commit_sha)

    assert commands == [["git", "fetch", "origin", commit_sha]]


def test_rechecker_surfaces_failed_command_stderr(tmp_path):
    def runner(command, **kwargs):
        raise subprocess.CalledProcessError(
            2,
            command,
            output="partial stdout",
            stderr="unrecognized arguments: --retention-days 30",
        )

    rechecker = ConfiguredRechecker(
        source_repository=tmp_path,
        worktree_root=tmp_path / "worktrees",
        runner=runner,
    )

    with pytest.raises(RuntimeError) as error:
        rechecker._run(["uv", "run", "tasklane-purge"], cwd=tmp_path)

    detail = str(error.value)
    assert "uv run tasklane-purge" in detail
    assert "unrecognized arguments: --retention-days 30" in detail


def test_recheck_executes_only_affected_probes_and_reuses_other_evidence(tmp_path, monkeypatch):
    context = demo_context(tmp_path)
    promises = [promise("P-014", PromiseKind.DELETION_DEADLINE, "customer personal data")]
    baseline = run_ledger(promises, context)

    purge = context.target_root / "tasklane" / "jobs" / "purge_tenant.py"
    purge.write_text('for table in ("users", "audit_events"):\n    delete(table)\n')
    storage = context.target_root / "infra" / "storage.tf"
    storage.write_text(
        'resource "aws_s3_bucket_lifecycle_configuration" "backups" {\n'
        "  rule { expiration { days = 30 } }\n"
        "}\n"
    )
    with sqlite3.connect(context.database) as connection:
        connection.execute("DELETE FROM audit_events")

    original = orchestrator.execute_probe
    executed = []

    def recording_executor(probe, probe_context):
        executed.append(probe.id)
        return original(probe, probe_context)

    monkeypatch.setattr(orchestrator, "execute_probe", recording_executor)

    result = recheck_ledger(
        baseline,
        context,
        affected_probe_ids=[
            "P-014-static-purge",
            "P-014-data-audit_events",
            "P-014-config-backups",
        ],
    )

    assert result.reports[0].verdict is Verdict.HOLDS
    assert executed == [
        "P-014-static-purge",
        "P-014-data-audit_events",
        "P-014-config-backups",
    ]
