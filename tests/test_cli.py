import json

from typer.testing import CliRunner

from ledger.cli import app
from ledger.llm import AzureJsonBackend
from ledger.models import Promise, PromiseKind, SourceSpan
from tests.test_orchestrator import demo_context, promise


def test_run_command_prints_ledger_and_writes_json_evidence(tmp_path):
    context = demo_context(tmp_path / "target")
    promises = [
        promise("P-014", PromiseKind.DELETION_DEADLINE, "customer personal data"),
        promise("P-017", PromiseKind.RETENTION_LIMIT, "database snapshots"),
        Promise(
            id="P-031",
            kind=PromiseKind.NOTICE_PERIOD,
            actor="Tasklane",
            object="subprocessor list",
            deadline_days=30,
            source=SourceSpan(
                document="Northwind_DPA_v3.pdf",
                clause="11.3",
                text="notify customers 30 days before adding a subprocessor",
            ),
        ),
    ]
    promises_path = tmp_path / "promises.json"
    promises_path.write_text(json.dumps([item.model_dump(mode="json") for item in promises]))
    output = tmp_path / "run.json"

    result = CliRunner().invoke(
        app,
        [
            "run",
            "--target",
            str(context.target_root),
            "--database",
            str(context.database),
            "--promises",
            str(promises_path),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "P-014  violated" in result.output
    assert "P-017  holds" in result.output
    assert "P-031  unverifiable" in result.output
    evidence = json.loads(output.read_text())
    assert [report["verdict"] for report in evidence["reports"]] == [
        "violated",
        "holds",
        "unverifiable",
    ]


def test_extract_command_loads_multiple_documents_and_writes_promises(tmp_path, monkeypatch):
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    first.write_text("Delete customer data within 30 days.")
    second.write_text("Store European customer data only in eu-west-1.")
    payloads = iter(
        [
            {
                "promises": [
                    {
                        "kind": "deletion_deadline",
                        "actor": "Tasklane",
                        "object": "customer data",
                        "includes": [],
                        "trigger": "contract.terminated",
                        "deadline_days": 30,
                        "clause": "7.2",
                        "text": "Delete customer data within 30 days.",
                    }
                ]
            },
            {
                "promises": [
                    {
                        "kind": "data_residency",
                        "actor": "Tasklane",
                        "object": "European customer data",
                        "includes": [],
                        "trigger": None,
                        "deadline_days": None,
                        "clause": "9.1",
                        "text": "Store European customer data only in eu-west-1.",
                    }
                ]
            },
        ]
    )

    class StubBackend:
        def complete_json(self, system: str, user: str) -> str:
            return json.dumps(next(payloads))

    monkeypatch.setattr(
        AzureJsonBackend,
        "from_env",
        classmethod(lambda cls: StubBackend()),
    )
    output = tmp_path / "promises.json"

    result = CliRunner().invoke(
        app,
        [
            "extract",
            "--document",
            str(first),
            "--document",
            str(second),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Extracted 2 promises" in result.output
    promises = json.loads(output.read_text())
    assert [item["id"] for item in promises] == ["P-001", "P-002"]
    assert [item["source"]["document"] for item in promises] == ["first.md", "second.md"]
