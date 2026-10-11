import json
from pathlib import Path

import pytest

from ledger.models import Promise
from ledger.registry import assign_canonical_ids, load_registry

REPOSITORY_ROOT = Path(__file__).parents[1]


def test_registry_assigns_all_nine_live_extractions_to_canonical_ids():
    extracted = [
        Promise.model_validate(item)
        for item in json.loads(
            (REPOSITORY_ROOT / "evidence" / "promises_extracted.json").read_text()
        )
    ]
    registry = load_registry(REPOSITORY_ROOT / "contracts" / "id_registry.json")

    assigned = assign_canonical_ids(extracted, registry)

    assert [promise.id for promise in assigned] == [
        "P-014",
        "P-017",
        "P-021",
        "P-031",
        "P-040",
        "P-041",
        "P-042",
        "P-043",
        "P-044",
    ]


def test_registry_rejects_an_unrecognized_extraction():
    extracted = Promise.model_validate(
        {
            "id": "P-001",
            "kind": "notice_period",
            "actor": "Tasklane",
            "object": "incident notices",
            "source": {
                "document": "unknown.pdf",
                "clause": "2.1",
                "text": "notify within one day",
            },
        }
    )

    with pytest.raises(ValueError, match="No canonical promise id"):
        assign_canonical_ids([extracted], {})


def test_registry_uses_unique_clause_candidate_when_model_kind_drifts():
    extracted = Promise.model_validate(
        {
            "id": "P-001",
            "kind": "deletion_deadline",
            "actor": "Tasklane",
            "object": "customer personal data and backups",
            "deadline_days": 90,
            "source": {
                "document": "privacy_policy.md",
                "clause": "5. Data retention",
                "text": "may retain customer personal data and backups for up to 90 days",
            },
        }
    )
    registry = {"privacy_policy.md|5|retention_limit": "P-044"}

    assigned = assign_canonical_ids([extracted], registry)

    assert assigned[0].id == "P-044"
    assert assigned[0].kind.value == "retention_limit"


def test_registry_merges_split_extractions_from_the_same_clause():
    items = [
        Promise.model_validate(
            {
                "id": f"P-00{index}",
                "kind": "retention_limit",
                "actor": "Tasklane",
                "object": object_name,
                "includes": [object_name] if object_name == "backups" else [],
                "deadline_days": 90,
                "source": {
                    "document": "privacy_policy.md",
                    "clause": "5. Data retention",
                    "text": "retain customer personal data and backups for up to 90 days",
                },
            }
        )
        for index, object_name in enumerate(
            ["customer personal data", "backups"],
            start=1,
        )
    ]
    registry = {"privacy_policy.md|5|retention_limit": "P-044"}

    assigned = assign_canonical_ids(items, registry)

    assert len(assigned) == 1
    assert assigned[0].id == "P-044"
    assert assigned[0].object == "customer personal data and backups"
    assert assigned[0].includes == ["backups"]
