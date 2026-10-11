import json

import pytest

from ledger.agents.compiler_agent import compile_checks_with_agent
from ledger.models import AssetMap, PromiseKind
from tests.test_orchestrator import promise


class StubBackend:
    def __init__(self, selected_probe_ids):
        self.selected_probe_ids = selected_probe_ids

    def complete_json(self, system: str, user: str) -> str:
        assert "safe candidate probes" in system
        assert "P-014-static-purge" in user
        return json.dumps(
            {
                "selected_probe_ids": self.selected_probe_ids,
                "grounding_notes": "Deletion covers every tenant table and backups.",
            }
        )


def test_compiler_agent_selects_validated_grounded_probe_candidates():
    assets = AssetMap(
        tenant_tables=["users", "audit_events"],
        source_files=["tasklane/jobs/purge_tenant.py"],
        terraform_files=["infra/storage.tf"],
    )
    deletion = promise("P-014", PromiseKind.DELETION_DEADLINE, "customer personal data")
    expected_ids = [
        "P-014-static-purge",
        "P-014-data-users",
        "P-014-data-audit_events",
        "P-014-config-backups",
    ]

    result = compile_checks_with_agent(deletion, assets, StubBackend(expected_ids))

    assert [probe.id for probe in result.probes] == expected_ids
    assert result.reasoning == "Deletion covers every tenant table and backups."


def test_compiler_agent_rejects_omitted_required_grounded_probe():
    assets = AssetMap(
        tenant_tables=["users", "audit_events"],
        source_files=["tasklane/jobs/purge_tenant.py"],
        terraform_files=["infra/storage.tf"],
    )
    deletion = promise("P-014", PromiseKind.DELETION_DEADLINE, "customer personal data")

    with pytest.raises(ValueError, match="must select every required safe probe"):
        compile_checks_with_agent(
            deletion,
            assets,
            StubBackend(["P-014-static-purge"]),
        )


def test_compiler_agent_accepts_model_reordering_but_preserves_candidate_order():
    assets = AssetMap(
        tenant_tables=["users", "audit_events"],
        source_files=["tasklane/jobs/purge_tenant.py"],
        terraform_files=["infra/storage.tf"],
    )
    deletion = promise("P-014", PromiseKind.DELETION_DEADLINE, "customer personal data")
    expected_ids = [
        "P-014-static-purge",
        "P-014-data-users",
        "P-014-data-audit_events",
        "P-014-config-backups",
    ]

    result = compile_checks_with_agent(
        deletion,
        assets,
        StubBackend(list(reversed(expected_ids))),
    )

    assert [probe.id for probe in result.probes] == expected_ids
