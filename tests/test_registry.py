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
