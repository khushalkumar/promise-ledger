import json

import pytest

from ledger.agents.extractor import extract_promises
from ledger.documents import LoadedDocument, load_document
from ledger.llm import AzureConfig
from ledger.models import PromiseKind


class StubBackend:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return json.dumps(self.payload)


def test_load_document_preserves_markdown_source(tmp_path):
    path = tmp_path / "privacy_policy.md"
    path.write_text("# Privacy policy\n\nRetain backups for up to 90 days.\n")

    document = load_document(path)

    assert document.name == "privacy_policy.md"
    assert "Retain backups for up to 90 days." in document.text


def test_extract_promises_validates_and_assigns_stable_ids():
    backend = StubBackend(
        {
            "promises": [
                {
                    "kind": "deletion_deadline",
                    "actor": "Tasklane",
                    "object": "customer personal data",
                    "includes": ["backups"],
                    "trigger": "contract.terminated",
                    "deadline_days": 30,
                    "clause": "7.2",
                    "text": "delete customer personal data within 30 days",
                },
                {
                    "kind": "data_residency",
                    "actor": "Tasklane",
                    "object": "European customer personal data",
                    "includes": [],
                    "trigger": None,
                    "deadline_days": None,
                    "clause": "9.1",
                    "text": "stored and processed only in eu-west-1",
                },
            ]
        }
    )
    document = LoadedDocument(name="Northwind_DPA_v3.pdf", text="contract text")

    promises = extract_promises(document, backend, starting_index=14)

    assert [promise.id for promise in promises] == ["P-014", "P-015"]
    assert promises[0].kind is PromiseKind.DELETION_DEADLINE
    assert promises[0].source.document == "Northwind_DPA_v3.pdf"
    assert promises[1].source.clause == "9.1"
    assert "contract text" in backend.calls[0][1]


def test_extract_promises_rejects_non_json_model_output():
    class InvalidBackend:
        def complete_json(self, system: str, user: str) -> str:
            return "not json"

    with pytest.raises(ValueError, match="valid JSON"):
        extract_promises(LoadedDocument(name="contract.md", text="terms"), InvalidBackend())


@pytest.mark.parametrize(
    ("kind", "object_name"),
    [
        ("feature_entitlement", "SSO configuration"),
        ("availability_slo", "monthly service availability"),
        ("encryption_at_rest", "customer data"),
        ("admin_mfa", "administrative accounts"),
    ],
)
def test_extract_promises_supports_msa_commitment_kinds(kind, object_name):
    backend = StubBackend(
        {
            "promises": [
                {
                    "kind": kind,
                    "actor": "Tasklane",
                    "object": object_name,
                    "includes": [],
                    "trigger": None,
                    "deadline_days": None,
                    "clause": "8.1",
                    "text": f"Tasklane commits to {object_name}.",
                }
            ]
        }
    )

    promises = extract_promises(LoadedDocument(name="msa.pdf", text="terms"), backend)

    assert promises[0].kind.value == kind


def test_azure_config_reports_missing_names_without_values(monkeypatch):
    for name in (
        "PROMISE_LEDGER_AZURE_ENDPOINT",
        "PROMISE_LEDGER_AZURE_API_KEY",
        "PROMISE_LEDGER_AZURE_DEPLOYMENT",
        "PROMISE_LEDGER_AZURE_API_VERSION",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValueError) as error:
        AzureConfig.from_env()

    message = str(error.value)
    assert "PROMISE_LEDGER_AZURE_ENDPOINT" in message
    assert "PROMISE_LEDGER_AZURE_API_KEY" in message
    assert "sk-" not in message
