import json

from ledger import benchmark as benchmark_module
from ledger.benchmark import _normalize_freeform_probes, compare_compilers
from ledger.models import AssetMap, Probe, ProbeKind, PromiseKind
from ledger.orchestrator import run_ledger
from tests.test_orchestrator import demo_context, promise


class V1Backend:
    def complete_json(self, system: str, user: str) -> str:
        assert "free-form" in system.lower()
        assert '"expected_verdict"' not in user
        assert "safe_candidate_probes" not in user
        return json.dumps({"probes": [], "reasoning": "No safe plan produced."})


class V2Backend:
    def complete_json(self, system: str, user: str) -> str:
        assert "safe candidate probes" in system
        request = json.loads(user)
        return json.dumps(
            {
                "selected_probe_ids": [
                    probe["id"] for probe in request["safe_candidate_probes"]
                ],
                "grounding_notes": "Every grounded check is required.",
            }
        )


def test_freeform_plan_is_canonicalized_and_cannot_invent_paths():
    deletion = promise("P-014", PromiseKind.DELETION_DEADLINE, "customer personal data")
    assets = AssetMap(
        tenant_tables=[],
        source_files=["tasklane/jobs/purge_tenant.py"],
        terraform_files=[],
    )
    proposed = Probe(
        id="whatever-the-model-invented",
        kind=ProbeKind.STATIC,
        template="static.purge_covers_tables",
        params={"path": "tasklane/jobs/purge_tenant.py", "required_tables": []},
        depends_on=["tasklane/jobs/purge_tenant.py", "invented-dependency"],
    )

    normalized = _normalize_freeform_probes(deletion, assets, [proposed])

    assert normalized[0].id == "P-014-v1-1-static-purge_covers_tables"
    assert normalized[0].depends_on == ["tasklane/jobs/purge_tenant.py"]


def test_freeform_plan_rejects_ungrounded_paths():
    import pytest

    deletion = promise("P-014", PromiseKind.DELETION_DEADLINE, "customer personal data")
    proposed = Probe(
        id="probe",
        kind=ProbeKind.STATIC,
        template="static.purge_covers_tables",
        params={"path": "outside/repository.py", "required_tables": []},
        depends_on=[],
    )

    with pytest.raises(ValueError, match="ungrounded path"):
        _normalize_freeform_probes(
            deletion,
            AssetMap(tenant_tables=[], source_files=[], terraform_files=[]),
            [proposed],
        )


def test_real_benchmark_executes_independent_llm_v1_and_grounded_v2(tmp_path):
    context = demo_context(tmp_path)
    promises = [
        promise("P-014", PromiseKind.DELETION_DEADLINE, "customer personal data"),
        promise("P-017", PromiseKind.RETENTION_LIMIT, "database snapshots"),
        promise("P-031", PromiseKind.NOTICE_PERIOD, "subprocessor list"),
    ]
    baseline = run_ledger(promises, context)

    benchmark = compare_compilers(
        baseline,
        context,
        v1_backend=V1Backend(),
        v2_backend=V2Backend(),
    )

    assert benchmark.cases == 4
    assert benchmark.v1.mismatches == 2
    assert benchmark.v1.llm_calls == 4
    assert benchmark.v2.mismatches == 0
    assert benchmark.v2.llm_calls == 4
    assert benchmark.v1.latency_ms >= 0
    assert benchmark.v2.latency_ms >= 0
    assert [case.promise_id for case in benchmark.details] == [
        "P-014",
        "P-017",
        "P-031",
        "P-050",
    ]


def test_benchmark_keeps_the_active_neatlogs_trace_id(monkeypatch, tmp_path):
    trace_id = "abcdef0123456789abcdef0123456789"
    monkeypatch.setattr(benchmark_module, "current_trace_id", lambda: trace_id)
    context = demo_context(tmp_path)
    baseline = run_ledger(
        [promise("P-014", PromiseKind.DELETION_DEADLINE, "customer personal data")],
        context,
    )
    benchmark = compare_compilers(
        baseline,
        context,
        v1_backend=V1Backend(),
        v2_backend=V2Backend(),
    )

    assert benchmark.trace_id == trace_id
