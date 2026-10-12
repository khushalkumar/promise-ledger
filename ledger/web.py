from __future__ import annotations

import hmac
import json
import os
import re
from collections import Counter
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field

from ledger.agent_service import AgentRunController, TriggerKind
from ledger.store import RunStore

PACKAGE_ROOT = Path(__file__).parent


class TriggerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_repository: str | None = Field(default=None, max_length=200)
    ref: str | None = Field(default=None, max_length=300)
    sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")


def create_app(
    evidence_path: Path | None = None,
    *,
    store: RunStore | None = None,
    trace_url_template: str = "https://app.neatlogs.com/traces/{trace_id}",
    agent_controller: AgentRunController | None = None,
    trigger_token: str | None = None,
) -> FastAPI:
    if evidence_path is None and store is None:
        raise ValueError("an evidence path or durable store is required")
    app = FastAPI(title="Promise Ledger")
    app.mount("/static", StaticFiles(directory=PACKAGE_ROOT / "static"), name="static")
    templates = Jinja2Templates(directory=PACKAGE_ROOT / "templates")

    @app.get("/healthz")
    def health() -> dict[str, str]:
        payload = {"status": "ok"}
        revision = os.getenv("RENDER_GIT_COMMIT")
        if revision:
            payload["revision"] = revision
        return payload

    @app.get("/", response_class=HTMLResponse)
    def ledger_page(request: Request) -> HTMLResponse:
        evidence, evidence_name, candidate = _load_ui_evidence(evidence_path, store)
        reports = evidence["reports"]
        for report in reports:
            for run in report["runs"]:
                run["effective"] = (
                    run["fallback"]
                    if run["primary"]["outcome"] == "error" and run["fallback"]
                    else run["primary"]
                )
                trace_id = run["effective"].get("trace_id")
                run["effective"]["trace_url"] = _trace_url(
                    trace_id,
                    trace_url_template,
                )
        verdict_counts = Counter(report["verdict"] for report in reports)
        context = {
            "request": request,
            "reports": reports,
            "conflicts": evidence["conflicts"],
            "counts": verdict_counts,
            "red_signals": _red_signal_count(evidence),
            "document_count": len(
                {report["promise"]["source"]["document"] for report in reports}
            ),
            "evidence_name": evidence_name,
            "candidate": candidate,
        }
        return templates.TemplateResponse(request=request, name="ledger.html", context=context)

    @app.get("/api/runs/latest")
    def latest_run() -> dict[str, object]:
        evidence, evidence_name = _load_evidence(evidence_path, store)
        return {"run_id": evidence_name, "ledger": evidence}

    @app.post("/api/agent-runs", status_code=status.HTTP_202_ACCEPTED)
    def start_agent_run(request: Request) -> dict[str, str]:
        _authorize_agent_request(request, trigger_token)
        if agent_controller is None:
            raise HTTPException(status_code=503, detail="Autonomous runs are not enabled")
        try:
            return agent_controller.start()
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/triggers/{trigger_kind}", status_code=status.HTTP_202_ACCEPTED)
    def start_triggered_agent_run(
        trigger_kind: TriggerKind,
        trigger_request: TriggerRequest,
        request: Request,
    ) -> dict[str, object]:
        _authorize_agent_request(request, trigger_token)
        if agent_controller is None:
            raise HTTPException(status_code=503, detail="Autonomous runs are not enabled")
        try:
            return agent_controller.start(
                trigger_kind=trigger_kind,
                trigger_payload=trigger_request.model_dump(exclude_none=True),
            )
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/agent-runs/status")
    def agent_run_status(request: Request) -> dict[str, object]:
        _authorize_agent_request(request, trigger_token)
        if agent_controller is None:
            raise HTTPException(status_code=503, detail="Autonomous runs are not enabled")
        payload: dict[str, object] = agent_controller.status()
        run_id = payload.get("run_id")
        if store is not None and isinstance(run_id, str) and run_id:
            workflow_run = store.get_run(run_id)
            if workflow_run is not None:
                payload["stage"] = workflow_run.stage.value
                payload["events"] = [
                    {
                        "stage": event.stage.value,
                        "payload": event.payload,
                    }
                    for event in workflow_run.events
                ]
        return payload

    return app


def _trace_url(trace_id: object, template: str) -> str | None:
    if not isinstance(trace_id, str) or re.fullmatch(r"[0-9a-f]{32}", trace_id) is None:
        return None
    return template.format(trace_id=trace_id)


def _load_evidence(
    evidence_path: Path | None,
    store: RunStore | None,
) -> tuple[dict[str, object], str]:
    if store is not None:
        latest = store.latest_ledger_result()
        if latest is not None:
            run_id, ledger = latest
            return ledger.model_dump(mode="json"), run_id
    if evidence_path is None:
        raise HTTPException(status_code=503, detail="No completed ledger run is available")
    return json.loads(evidence_path.read_text()), evidence_path.name


def _load_ui_evidence(
    evidence_path: Path | None,
    store: RunStore | None,
) -> tuple[dict[str, object], str, dict[str, object] | None]:
    evidence, evidence_name = _load_evidence(evidence_path, store)
    if store is None:
        return evidence, evidence_name, None

    workflow = store.get_run(evidence_name)
    baseline = store.ledger_result(evidence_name, phase="baseline")
    pull_requests = [] if workflow is None else [
        url
        for event in workflow.events
        for url in event.payload.get("pull_requests", [])
        if isinstance(url, str)
    ]
    if baseline is None or not pull_requests:
        return evidence, evidence_name, None

    candidate = {
        "red_signals": _red_signal_count(evidence),
        "pull_requests": pull_requests,
    }
    return baseline.model_dump(mode="json"), evidence_name, candidate


def _red_signal_count(evidence: dict[str, object]) -> int:
    reports = evidence["reports"]
    conflicts = evidence["conflicts"]
    return sum(report["verdict"] == "violated" for report in reports) + sum(
        conflict["verdict"] == "violated" for conflict in conflicts
    )


def _authorize_agent_request(request: Request, trigger_token: str | None) -> None:
    authorization = request.headers.get("authorization", "")
    prefix = "Bearer "
    supplied = authorization[len(prefix) :] if authorization.startswith(prefix) else ""
    if not trigger_token or not supplied or not hmac.compare_digest(supplied, trigger_token):
        raise HTTPException(status_code=401, detail="Invalid autonomous-run token")


def main() -> None:
    state_database = os.getenv("PROMISE_LEDGER_STATE_DATABASE")
    evidence_path = Path(os.getenv("PROMISE_LEDGER_RUN", "evidence/run_live_audit.json"))
    store = None
    if state_database:
        store = RunStore(state_database)
    agent_controller = None
    trigger_token = os.getenv("PROMISE_LEDGER_TRIGGER_TOKEN")
    if os.getenv("PROMISE_LEDGER_ENABLE_AGENT", "").lower() == "true":
        if not trigger_token:
            raise ValueError("PROMISE_LEDGER_TRIGGER_TOKEN is required when agent runs are enabled")
        agent_controller = AgentRunController(
            command=[os.getenv("PROMISE_LEDGER_AGENT_COMMAND", "/app/scripts/render-agent-run.sh")]
        )
    host = os.getenv("PROMISE_LEDGER_HOST", "127.0.0.1")
    port = int(os.getenv("PROMISE_LEDGER_PORT") or os.getenv("PORT", "8000"))
    trace_url_template = os.getenv(
        "NEATLOGS_TRACE_URL_TEMPLATE",
        "https://app.neatlogs.com/traces/{trace_id}",
    )
    uvicorn.run(
        create_app(
            evidence_path,
            store=store,
            trace_url_template=trace_url_template,
            agent_controller=agent_controller,
            trigger_token=trigger_token,
        ),
        host=host,
        port=port,
    )
