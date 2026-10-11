from __future__ import annotations

import json
import subprocess
import tempfile
from collections.abc import Callable
from typing import Any

from ledger.models import PullRequestRef

Runner = Callable[..., subprocess.CompletedProcess[str]]


class GhPullRequests:
    def __init__(self, repository: str, *, runner: Runner = subprocess.run) -> None:
        self.repository = repository
        self.runner = runner

    def find_open(self, branch: str) -> PullRequestRef | None:
        result = self._run(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                self.repository,
                "--head",
                branch,
                "--state",
                "open",
                "--json",
                "number,url,headRefName,headRefOid",
            ]
        )
        requests: list[dict[str, Any]] = json.loads(result.stdout)
        if not requests:
            return None
        request = requests[0]
        return PullRequestRef(
            number=int(request["number"]),
            url=str(request["url"]),
            branch=str(request["headRefName"]),
            commit_sha=str(request["headRefOid"]),
            created=False,
        )

    def ensure_open(
        self,
        *,
        branch: str,
        title: str,
        body: str,
        commit_sha: str,
        draft: bool,
    ) -> PullRequestRef:
        existing = self.find_open(branch)
        if existing is not None:
            return existing

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", encoding="utf-8") as body_file:
            body_file.write(body)
            body_file.flush()
            command = [
                "gh",
                "pr",
                "create",
                "--repo",
                self.repository,
                "--base",
                "main",
                "--head",
                branch,
                "--title",
                title,
                "--body-file",
                body_file.name,
            ]
            if draft:
                command.append("--draft")
            created = self._run(command)

        url = created.stdout.strip()
        viewed = self._run(
            [
                "gh",
                "pr",
                "view",
                url,
                "--repo",
                self.repository,
                "--json",
                "number,url,headRefName,headRefOid",
            ]
        )
        request = json.loads(viewed.stdout)
        return PullRequestRef(
            number=int(request["number"]),
            url=str(request["url"]),
            branch=str(request["headRefName"]),
            commit_sha=str(request.get("headRefOid") or commit_sha),
            created=True,
        )

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        return self.runner(command, check=True, capture_output=True, text=True)
