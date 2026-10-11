from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ledger.store import RunStore

PACKAGE_ROOT = Path(__file__).parent


def create_app(
    evidence_path: Path | None = None,
    *,
    store: RunStore | None = None,
    trace_url_template: str = "https://app.neatlogs.com/traces/{trace_id}",
) -> FastAPI:
    if evidence_path is None and store is None:
        raise ValueError("an evidence path or durable store is required")
    app = FastAPI(title="Promise Ledger")
    app.mount("/static", StaticFiles(directory=PACKAGE_ROOT / "static"), name="static")
    templates = Jinja2Templates(directory=PACKAGE_ROOT / "templates")

    @app.get("/", response_class=HTMLResponse)
    def ledger_page(request: Request) -> HTMLResponse:
        evidence, evidence_name = _load_evidence(evidence_path, store)
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
        conflict_count = sum(
            conflict["verdict"] == "violated" for conflict in evidence["conflicts"]
        )
        context = {
            "request": request,
            "reports": reports,
            "conflicts": evidence["conflicts"],
            "counts": verdict_counts,
            "red_signals": verdict_counts["violated"] + conflict_count,
            "document_count": len(
                {report["promise"]["source"]["document"] for report in reports}
            ),
            "evidence_name": evidence_name,
        }
        return templates.TemplateResponse(request=request, name="ledger.html", context=context)

    @app.get("/api/runs/latest")
    def latest_run() -> dict[str, object]:
        evidence, evidence_name = _load_evidence(evidence_path, store)
        return {"run_id": evidence_name, "ledger": evidence}

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
        if latest is None:
            raise HTTPException(status_code=503, detail="No completed ledger run is available")
        run_id, ledger = latest
        return ledger.model_dump(mode="json"), run_id
    assert evidence_path is not None
    return json.loads(evidence_path.read_text()), evidence_path.name


def main() -> None:
    state_database = os.getenv("PROMISE_LEDGER_STATE_DATABASE")
    evidence_path = None
    store = None
    if state_database:
        store = RunStore(state_database)
    else:
        evidence_path = Path(os.getenv("PROMISE_LEDGER_RUN", "evidence/run_live_audit.json"))
    host = os.getenv("PROMISE_LEDGER_HOST", "127.0.0.1")
    port = int(os.getenv("PROMISE_LEDGER_PORT", "8000"))
    trace_url_template = os.getenv(
        "NEATLOGS_TRACE_URL_TEMPLATE",
        "https://app.neatlogs.com/traces/{trace_id}",
    )
    uvicorn.run(
        create_app(evidence_path, store=store, trace_url_template=trace_url_template),
        host=host,
        port=port,
    )
