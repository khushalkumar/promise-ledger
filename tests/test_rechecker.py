import json
import subprocess
import sys

from ledger.integrations.recheck import ConfiguredRechecker
from ledger.models import PromiseKind, Verdict
from ledger.orchestrator import run_ledger
from tests.test_orchestrator import demo_context, promise


def test_configured_rechecker_applies_pr_commits_runs_target_commands_and_rechecks(tmp_path):
    repository = tmp_path / "target"
    context = demo_context(repository)
    seed_script = repository / "seed_recheck.py"
    seed_script.write_text(
        "import sqlite3, sys\n"
        "db = sys.argv[1]\n"
        "with sqlite3.connect(db) as c:\n"
        " c.executescript(\"\"\"CREATE TABLE tenants (id TEXT PRIMARY KEY, terminated_at TEXT);\n"
        "CREATE TABLE users (id INTEGER PRIMARY KEY, tenant_id TEXT);\n"
        "CREATE TABLE audit_events (id INTEGER PRIMARY KEY, tenant_id TEXT);\n"
        "INSERT INTO tenants VALUES ('expired', '2026-08-01T00:00:00+00:00');\n"
        "INSERT INTO audit_events VALUES (1, 'expired');\"\"\")\n"
    )
    effect_script = repository / "effect_recheck.py"
    effect_script.write_text(
        "import sqlite3, sys\n"
        "with sqlite3.connect(sys.argv[1]) as c:\n"
        " c.execute('DELETE FROM audit_events')\n"
    )
    (repository / ".promise-ledger.json").write_text(
        json.dumps(
            {
                "version": 1,
                "verification": {
                    "test_command": [sys.executable, "-c", "print('tests passed')"],
                    "seed_command": [sys.executable, "seed_recheck.py", "{database}"],
                    "effect_commands": [
                        [sys.executable, "effect_recheck.py", "{database}"]
                    ],
                },
            }
        )
    )
    remote = tmp_path / "remote.git"
    _git(["init", "--bare", str(remote)], cwd=tmp_path)
    _git(["init", "-b", "main"], cwd=repository)
    _git(["config", "user.name", "Khushal Kumar"], cwd=repository)
    _git(["config", "user.email", "kkhushal1531@gmail.com"], cwd=repository)
    _git(["add", "."], cwd=repository)
    _git(["commit", "-m", "initial"], cwd=repository)
    _git(["remote", "add", "origin", str(remote)], cwd=repository)
    _git(["push", "-u", "origin", "main"], cwd=repository)
    baseline = run_ledger(
        [promise("P-014", PromiseKind.DELETION_DEADLINE, "customer personal data")],
        context,
    )

    _git(["switch", "-c", "fix-code"], cwd=repository)
    (repository / "tasklane" / "jobs" / "purge_tenant.py").write_text(
        'for table in ("users", "audit_events"):\n    delete(table)\n'
    )
    _git(["add", "tasklane/jobs/purge_tenant.py"], cwd=repository)
    _git(["commit", "-m", "fix purge"], cwd=repository)
    code_commit = _git(["rev-parse", "HEAD"], cwd=repository).stdout.strip()
    _git(["switch", "main"], cwd=repository)

    _git(["switch", "-c", "fix-config"], cwd=repository)
    (repository / "infra" / "storage.tf").write_text(
        'resource "aws_s3_bucket_lifecycle_configuration" "backups" {\n'
        "  rule { expiration { days = 30 } }\n"
        "}\n"
    )
    _git(["add", "infra/storage.tf"], cwd=repository)
    _git(["commit", "-m", "fix retention"], cwd=repository)
    config_commit = _git(["rev-parse", "HEAD"], cwd=repository).stdout.strip()
    _git(["switch", "main"], cwd=repository)

    rechecker = ConfiguredRechecker(repository, tmp_path / "rechecks")
    result = rechecker.recheck(
        baseline=baseline,
        affected_probe_ids=[
            "P-014-static-purge",
            "P-014-data-audit_events",
            "P-014-config-backups",
        ],
        commit_shas=[code_commit, config_commit],
    )

    assert result.reports[0].verdict is Verdict.HOLDS
    assert not list((tmp_path / "rechecks").glob("worktree-*"))


def _git(command, *, cwd):
    return subprocess.run(
        ["git", *command],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
