from __future__ import annotations

import re
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from ledger.models import LedgerRun
from ledger.orchestrator import recheck_ledger
from ledger.probes.executors import ProbeContext

Runner = Callable[..., subprocess.CompletedProcess[str]]


class VerificationConfig(BaseModel):
    test_command: list[str]
    seed_command: list[str]
    effect_commands: list[list[str]]


class TargetConfig(BaseModel):
    version: int
    verification: VerificationConfig


class ConfiguredRechecker:
    def __init__(
        self,
        source_repository: Path,
        worktree_root: Path,
        *,
        runner: Runner = subprocess.run,
    ) -> None:
        self.source_repository = source_repository.resolve()
        self.worktree_root = worktree_root.resolve()
        self.runner = runner

    def recheck(
        self,
        *,
        baseline: LedgerRun,
        affected_probe_ids: list[str],
        commit_shas: list[str],
    ) -> LedgerRun:
        self.worktree_root.mkdir(parents=True, exist_ok=True)
        worktree = Path(
            tempfile.mkdtemp(prefix="worktree-", dir=self.worktree_root)
        )
        worktree.rmdir()
        added = False
        try:
            self._run(["git", "fetch", "origin", "main"], cwd=self.source_repository)
            self._run(
                ["git", "worktree", "add", "--detach", str(worktree), "origin/main"],
                cwd=self.source_repository,
            )
            added = True
            for commit_sha in commit_shas:
                self._fetch_commit(commit_sha)
                self._cherry_pick(commit_sha, worktree)

            config = TargetConfig.model_validate_json(
                (worktree / ".promise-ledger.json").read_text()
            )
            if config.version != 1:
                raise ValueError(f"unsupported target config version: {config.version}")
            database = worktree / ".promise-ledger-recheck.db"
            self._run_command(config.verification.test_command, worktree, database)
            self._run_command(config.verification.seed_command, worktree, database)
            for command in config.verification.effect_commands:
                self._run_command(command, worktree, database)

            return recheck_ledger(
                baseline,
                ProbeContext(target_root=worktree, database=database),
                affected_probe_ids=affected_probe_ids,
            )
        finally:
            if added:
                self._run(
                    ["git", "worktree", "remove", "--force", str(worktree)],
                    cwd=self.source_repository,
                )
            elif worktree.exists():
                worktree.rmdir()

    def _run_command(self, command: list[str], worktree: Path, database: Path) -> None:
        expanded = [part.replace("{database}", str(database)) for part in command]
        self._run(expanded, cwd=worktree)

    def _cherry_pick(self, commit_sha: str, worktree: Path) -> None:
        self._run(
            [
                "git",
                "-c",
                "user.name=Khushal Kumar",
                "-c",
                "user.email=kkhushal1531@gmail.com",
                "cherry-pick",
                commit_sha,
            ],
            cwd=worktree,
        )

    def _fetch_commit(self, commit_sha: str) -> None:
        if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
            raise ValueError(f"invalid remediation commit SHA: {commit_sha}")
        self._run(
            ["git", "fetch", "origin", commit_sha],
            cwd=self.source_repository,
        )

    def _run(self, command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        return self.runner(
            command,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
