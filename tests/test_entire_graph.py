import json
from subprocess import CompletedProcess

from ledger.entire_graph import search_entire_graph


def test_entire_graph_search_returns_ranked_source_evidence(monkeypatch, tmp_path):
    payload = {
        "results": [
            {
                "rank": 1,
                "score": 38.1498,
                "file_path": "tasklane/jobs/purge_tenant.py",
                "start_line": 13,
                "end_line": 40,
                "symbol_name": "purge_expired_tenants",
            },
            {
                "rank": 2,
                "score": 27.6131,
                "file_path": "tests/test_fixture.py",
                "start_line": 27,
                "end_line": 55,
                "symbol_name": "test_purge_leaves_the_planted_audit_event_violation",
            },
        ]
    }
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr("ledger.entire_graph.subprocess.run", fake_run)

    hits = search_entire_graph(tmp_path, "tenant deletion purge job audit events")

    assert [hit.file_path for hit in hits] == [
        "tasklane/jobs/purge_tenant.py",
        "tests/test_fixture.py",
    ]
    assert hits[0].symbol_name == "purge_expired_tenants"
    assert captured["command"][:4] == ["entire", "graph", "search", "--repo"]
    assert captured["kwargs"]["timeout"] == 10


def test_entire_graph_search_fails_closed_when_cli_is_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "ledger.entire_graph.subprocess.run",
        lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError()),
    )

    assert search_entire_graph(tmp_path, "deletion") == []
