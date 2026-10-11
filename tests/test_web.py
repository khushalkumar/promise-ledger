import json

from fastapi.testclient import TestClient

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
                                    "trace_id": None,
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
