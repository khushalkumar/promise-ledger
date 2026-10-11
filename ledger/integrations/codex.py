from __future__ import annotations

import json
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from ledger.models import AgentChange, RootCause

Runner = Callable[..., subprocess.CompletedProcess[str]]


class AgentChangeOutput(BaseModel):
    summary: str
    changed_files: list[str]
    tests: list[str]


class CodexCodingAgent:
    def __init__(
        self,
        *,
        binary: str = "codex",
        runner: Runner = subprocess.run,
        timeout_seconds: int = 900,
    ) -> None:
        self.binary = binary
        self.runner = runner
        self.timeout_seconds = timeout_seconds

    def implement(self, *, worktree: Path, root_cause: RootCause, prompt: str) -> AgentChange:
        with tempfile.TemporaryDirectory(prefix="promise-ledger-codex-") as temporary:
            temporary_path = Path(temporary)
            schema_path = temporary_path / "result.schema.json"
            output_path = temporary_path / "result.json"
            schema_path.write_text(json.dumps(AgentChangeOutput.model_json_schema(), indent=2))
            command = [
                self.binary,
                "exec",
                "--json",
                "--approve-for-me",
                "--dangerously-bypass-hook-trust",
                "--cd",
                str(worktree),
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
                "-",
            ]
            try:
                completed = self.runner(
                    command,
                    input=prompt,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                )
            except subprocess.CalledProcessError as error:
                detail = (error.stderr or error.stdout or f"exit code {error.returncode}").strip()
                raise RuntimeError(f"Codex coding agent failed: {detail[-4000:]}") from error
            output = AgentChangeOutput.model_validate_json(output_path.read_text())

        for changed in output.changed_files:
            path = Path(changed)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"coding agent reported unsafe changed file: {changed}")
        return AgentChange(
            summary=output.summary,
            changed_files=output.changed_files,
            tests=output.tests,
            session_id=_thread_id(completed.stdout),
        )


def _thread_id(json_lines: str) -> str | None:
    for line in json_lines.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "thread.started" and event.get("thread_id"):
            return str(event["thread_id"])
    return None
