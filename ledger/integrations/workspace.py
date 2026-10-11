from __future__ import annotations

import re
import subprocess
from pathlib import Path


class GitWorkspace:
    def __init__(self, source_repository: Path, worktree_root: Path) -> None:
        self.source_repository = source_repository.resolve()
        self.worktree_root = worktree_root.resolve()

    def prepare(self, branch: str) -> Path:
        _validate_branch(branch)
        self._run(["git", "fetch", "origin", "main"], cwd=self.source_repository)
        target = self.worktree_root / branch.replace("/", "-")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            registered = self._run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=self.source_repository,
            ).stdout
            if f"worktree {target}" in registered:
                return target
            raise ValueError(f"worktree path already exists but is not registered: {target}")

        remote_branch = self._run(
            ["git", "ls-remote", "--heads", "origin", f"refs/heads/{branch}"],
            cwd=self.source_repository,
        ).stdout.strip()
        start = f"origin/{branch}" if remote_branch else "origin/main"
        self._run(
            ["git", "worktree", "add", "-B", branch, str(target), start],
            cwd=self.source_repository,
        )
        return target

    def changed_files(self, worktree: Path) -> list[str]:
        output = self._run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=worktree
        ).stdout
        return sorted(line[3:] for line in output.splitlines() if len(line) > 3)

    def commit_and_push(self, worktree: Path, *, branch: str, message: str) -> str:
        _validate_branch(branch)
        changed = self.changed_files(worktree)
        if not changed:
            return self._run(["git", "rev-parse", "HEAD"], cwd=worktree).stdout.strip()
        forbidden = [path for path in changed if _looks_secret(path)]
        if forbidden:
            raise ValueError(f"refusing to commit secret-like files: {', '.join(forbidden)}")
        self._run(["git", "add", "--", *changed], cwd=worktree)
        self._run(
            [
                "git",
                "-c",
                "user.name=Khushal Kumar",
                "-c",
                "user.email=kkhushal1531@gmail.com",
                "commit",
                "-m",
                message,
            ],
            cwd=worktree,
        )
        commit_sha = self._run(["git", "rev-parse", "HEAD"], cwd=worktree).stdout.strip()
        self._run(
            ["git", "push", "--set-upstream", "origin", f"HEAD:refs/heads/{branch}"],
            cwd=worktree,
        )
        return commit_sha

    @staticmethod
    def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)


def _validate_branch(branch: str) -> None:
    if not re.fullmatch(r"promise-ledger/[a-z0-9][a-z0-9._/-]{1,118}", branch):
        raise ValueError(f"unsafe remediation branch: {branch}")
    if ".." in branch or branch.endswith("/") or "//" in branch:
        raise ValueError(f"unsafe remediation branch: {branch}")


def _looks_secret(path: str) -> bool:
    name = Path(path).name.lower()
    return name == ".env" or name.endswith((".pem", ".key", ".p12", ".pfx"))
