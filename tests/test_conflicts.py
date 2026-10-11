from ledger.conflicts import detect_conflicts
from ledger.models import Promise, PromiseKind, SourceSpan, Verdict


def retention_promise(
    promise_id: str,
    *,
    kind: PromiseKind,
    object_name: str,
    days: int,
    document: str,
) -> Promise:
    return Promise(
        id=promise_id,
        kind=kind,
        actor="Tasklane",
        object=object_name,
        includes=["backups"],
        deadline_days=days,
        source=SourceSpan(
            document=document,
            clause="7.2" if days == 30 else "5",
            text=f"retain {object_name} for at most {days} days",
        ),
    )


def test_detects_cross_document_retention_conflict():
    dpa = retention_promise(
        "P-014",
        kind=PromiseKind.DELETION_DEADLINE,
        object_name="customer personal data",
        days=30,
        document="Northwind_DPA_v3.pdf",
    )
    policy = retention_promise(
        "P-044",
        kind=PromiseKind.RETENTION_LIMIT,
        object_name="customer personal data and backups",
        days=90,
        document="privacy_policy.md",
    )

    conflicts = detect_conflicts([dpa, policy])

    assert len(conflicts) == 1
    assert conflicts[0].id == "C-003"
    assert conflicts[0].promise_ids == ["P-014", "P-044"]
    assert conflicts[0].verdict is Verdict.VIOLATED
    assert "30 days" in conflicts[0].detail
    assert "90 days" in conflicts[0].detail


def test_does_not_conflict_when_promises_cover_different_objects():
    customer_data = retention_promise(
        "P-014",
        kind=PromiseKind.DELETION_DEADLINE,
        object_name="customer personal data",
        days=30,
        document="dpa.pdf",
    )
    snapshots = retention_promise(
        "P-017",
        kind=PromiseKind.RETENTION_LIMIT,
        object_name="database snapshots",
        days=90,
        document="operations.md",
    )

    assert detect_conflicts([customer_data, snapshots]) == []
