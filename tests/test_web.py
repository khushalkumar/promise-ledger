import json
import subprocess

from fastapi.testclient import TestClient

import ledger.web
from ledger.agent_service import AgentRunController
from ledger.models import LedgerRun
from ledger.store import RunStore
from ledger.web import create_app
from tests.test_investigator import _violated_report


def test_ledger_page_renders_verdict_evidence_and_conflicts(tmp_path):
    evidence = tmp_path / "run.json"
    evidence.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "promise": {
                            "id": "P-014",
                            "kind": "deletion_deadline",
                            "actor": "Tasklane",
                            "object": "customer personal data",
                            "includes": ["backups"],
                            "trigger": "contract.terminated",
                            "deadline_days": 30,
                            "source": {
                                "document": "Northwind_DPA_v3.pdf",
                                "clause": "7.2",
                                "text": "delete customer data within 30 days",
                            },
                        },
                        "probes": [],
                        "runs": [
                            {
                                "primary": {
                                    "probe_id": "P-014-data-audit_events",
                                    "outcome": "fail",
                                    "evidence_sha256": "abc123",
                                    "detail": "audit_events has 1284 rows past the deadline",
                                    "trace_id": "0123456789abcdef0123456789abcdef",
                                },
                                "fallback": None,
                            }
                        ],
                        "verdict": "violated",
                    }
                ],
                "conflicts": [
                    {
                        "id": "C-003",
                        "promise_ids": ["P-014", "P-044"],
                        "verdict": "violated",
                        "detail": "DPA limits data to 30 days, but policy allows 90 days",
                    }
                ],
            }
        )
    )

    response = TestClient(create_app(evidence)).get("/")

    assert response.status_code == 200
    assert "Promise Ledger" in response.text
    assert "P-014" in response.text
    assert "Northwind_DPA_v3.pdf" in response.text
    assert "audit_events has 1284 rows" in response.text
    assert "C-003" in response.text
    assert (
        'href="https://app.neatlogs.com/traces/0123456789abcdef0123456789abcdef"'
        in response.text
    )
    assert "Open trace" in response.text


def test_ledger_page_renders_latest_durable_run_without_json_file(tmp_path):
    store = RunStore(f"sqlite:///{tmp_path / 'state.db'}")
    store.create_run("run-cloud", target_repository="khushalkumar/tasklane-demo")
    store.save_ledger_result(
        "run-cloud",
        phase="final",
        ledger=LedgerRun(reports=[_violated_report()]),
    )

    response = TestClient(create_app(store=store)).get("/")

    assert response.status_code == 200
    assert "P-014" in response.text
    assert "run-cloud" in response.text


def test_health_endpoint_does_not_load_evidence(tmp_path):
    missing_evidence = tmp_path / "missing.json"

    response = TestClient(create_app(missing_evidence)).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_main_uses_render_port_when_promise_ledger_port_is_unset(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setenv("PROMISE_LEDGER_RUN", str(tmp_path / "run.json"))
    monkeypatch.delenv("PROMISE_LEDGER_PORT", raising=False)
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setattr(ledger.web.uvicorn, "run", lambda *args, **kwargs: calls.append(kwargs))

    ledger.web.main()

    assert calls == [{"host": "127.0.0.1", "port": 10000}]


def test_ledger_page_falls_back_to_saved_evidence_before_first_durable_run(tmp_path):
    evidence = tmp_path / "run.json"
    evidence.write_text(json.dumps({"reports": [], "conflicts": []}))
    store = RunStore(f"sqlite:///{tmp_path / 'state.db'}")

    response = TestClient(create_app(evidence, store=store)).get("/api/runs/latest")

    assert response.status_code == 200
    assert response.json()["run_id"] == "run.json"


def test_agent_run_trigger_requires_token_and_reports_completion(tmp_path):
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="Run completed", stderr="")

    controller = AgentRunController(
        command=["/app/scripts/render-agent-run.sh"],
        runner=runner,
        run_id_factory=lambda: "pl-render-test",
        synchronous=True,
    )
    evidence = tmp_path / "run.json"
    evidence.write_text(json.dumps({"reports": [], "conflicts": []}))
    client = TestClient(
        create_app(evidence, agent_controller=controller, trigger_token="top-secret")
    )

    unauthorized = client.post("/api/agent-runs")
    accepted = client.post(
        "/api/agent-runs", headers={"Authorization": "Bearer top-secret"}
    )
    status = client.get(
        "/api/agent-runs/status", headers={"Authorization": "Bearer top-secret"}
    )

    assert unauthorized.status_code == 401
    assert accepted.status_code == 202
    assert accepted.json() == {"run_id": "pl-render-test", "status": "completed"}
    assert status.status_code == 200
    assert status.json()["status"] == "completed"
    assert calls[0][1]["env"]["PROMISE_LEDGER_RUN_ID"] == "pl-render-test"


def test_agent_run_trigger_rejects_parallel_run(tmp_path):
    controller = AgentRunController(
        command=["ignored"],
        runner=lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0),
        run_id_factory=lambda: "pl-existing",
        synchronous=True,
    )
    controller._status = {"run_id": "pl-existing", "status": "running"}
    evidence = tmp_path / "run.json"
    evidence.write_text(json.dumps({"reports": [], "conflicts": []}))
    client = TestClient(
        create_app(evidence, agent_controller=controller, trigger_token="top-secret")
    )

    response = client.post(
        "/api/agent-runs", headers={"Authorization": "Bearer top-secret"}
    )

    assert response.status_code == 409
