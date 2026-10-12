from __future__ import annotations

import json
import os
import subprocess
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

Runner = Callable[..., subprocess.CompletedProcess[str]]


class TriggerKind(StrEnum):
    MANUAL = "manual"
    NEW_CONTRACT = "new_contract"
    DEPLOY = "deploy"
    INFRA_CHANGE = "infra_change"
    NIGHTLY = "nightly"


class AgentRunController:
    def __init__(
        self,
        *,
        command: list[str],
        runner: Runner = subprocess.run,
        run_id_factory: Callable[[], str] | None = None,
        synchronous: bool = False,
    ) -> None:
        self.command = command
        self.runner = runner
        self.run_id_factory = run_id_factory or _new_run_id
        self.synchronous = synchronous
        self._lock = threading.Lock()
        self._status: dict[str, object] = {"run_id": "", "status": "idle"}

    def start(
        self,
        *,
        trigger_kind: TriggerKind = TriggerKind.MANUAL,
        trigger_payload: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        with self._lock:
            if self._status["status"] == "running":
                raise RuntimeError("an autonomous run is already in progress")
            run_id = self.run_id_factory()
            self._status = {"run_id": run_id, "status": "running"}
            if trigger_kind is not TriggerKind.MANUAL:
                self._status["trigger"] = trigger_kind.value

        if self.synchronous:
            self._execute(run_id, trigger_kind, trigger_payload or {})
        else:
            threading.Thread(
                target=self._execute,
                args=(run_id, trigger_kind, trigger_payload or {}),
                daemon=True,
            ).start()
        return self.status()

    def status(self) -> dict[str, object]:
        with self._lock:
            return dict(self._status)

    def _execute(
        self,
        run_id: str,
        trigger_kind: TriggerKind,
        trigger_payload: dict[str, Any],
    ) -> None:
        environment = os.environ.copy()
        environment["PROMISE_LEDGER_RUN_ID"] = run_id
        environment["PROMISE_LEDGER_TRIGGER_KIND"] = trigger_kind.value
        environment["PROMISE_LEDGER_TRIGGER_PAYLOAD"] = json.dumps(
            trigger_payload,
            sort_keys=True,
        )
        try:
            completed = self.runner(
                self.command,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as error:  # pragma: no cover - defensive process boundary
            self._finish(run_id, "failed", f"{type(error).__name__}: {error}")
            return
        if completed.returncode == 0:
            self._finish(run_id, "completed")
            return
        detail = (completed.stderr or completed.stdout or "agent process failed")[-2000:]
        self._finish(run_id, "failed", detail)

    def _finish(self, run_id: str, status: str, detail: str | None = None) -> None:
        with self._lock:
            payload: dict[str, object] = {"run_id": run_id, "status": status}
            trigger = self._status.get("trigger")
            if trigger is not None:
                payload["trigger"] = trigger
            if detail:
                payload["detail"] = detail
            self._status = payload


def _new_run_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"pl-{timestamp}-{uuid4().hex[:8]}"
