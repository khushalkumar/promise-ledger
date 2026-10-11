from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

PACKAGE_ROOT = Path(__file__).parent


def create_app(evidence_path: Path) -> FastAPI:
    app = FastAPI(title="Promise Ledger")
    app.mount("/static", StaticFiles(directory=PACKAGE_ROOT / "static"), name="static")
    templates = Jinja2Templates(directory=PACKAGE_ROOT / "templates")

    @app.get("/", response_class=HTMLResponse)
    def ledger_page(request: Request) -> HTMLResponse:
        evidence = json.loads(evidence_path.read_text())
        reports = evidence["reports"]
        for report in reports:
            for run in report["runs"]:
                run["effective"] = (
                    run["fallback"]
                    if run["primary"]["outcome"] == "error" and run["fallback"]
                    else run["primary"]
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
            "evidence_name": evidence_path.name,
        }
        return templates.TemplateResponse(request=request, name="ledger.html", context=context)

    return app


def main() -> None:
    evidence_path = Path(os.getenv("PROMISE_LEDGER_RUN", "evidence/run_live_audit.json"))
    host = os.getenv("PROMISE_LEDGER_HOST", "127.0.0.1")
    port = int(os.getenv("PROMISE_LEDGER_PORT", "8000"))
    uvicorn.run(create_app(evidence_path), host=host, port=port)
