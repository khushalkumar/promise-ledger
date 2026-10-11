import sqlite3

from ledger.models import Promise, PromiseKind, SourceSpan, Verdict
from ledger.orchestrator import run_ledger
from ledger.probes.executors import ProbeContext


def promise(promise_id: str, kind: PromiseKind, object_name: str) -> Promise:
    return Promise(
        id=promise_id,
        kind=kind,
        actor="Tasklane",
        object=object_name,
        includes=["backups"] if promise_id == "P-014" else [],
        trigger="contract.terminated",
        deadline_days=30,
        source=SourceSpan(
            document="Northwind_DPA_v3.pdf",
            clause="7.2",
            text=f"contract clause for {promise_id}",
        ),
    )


def demo_context(tmp_path) -> ProbeContext:
    source = tmp_path / "tasklane" / "jobs" / "purge_tenant.py"
    source.parent.mkdir(parents=True)
    source.write_text('for table in ("users",):\n    delete(table)\n')

    infra = tmp_path / "infra"
    infra.mkdir()
    (infra / "storage.tf").write_text(
        'resource "aws_s3_bucket_lifecycle_configuration" "backups" {\n'
        '  rule { expiration { days = 90 } }\n'
        '}\n'
    )
    (infra / "database.tf").write_text(
        'resource "aws_db_instance" "primary" {\n'
        "  backup_retention_period = 30\n"
        "}\n"
    )

    database = tmp_path / "tasklane.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE tenants (id TEXT PRIMARY KEY, terminated_at TEXT);
            CREATE TABLE users (id INTEGER PRIMARY KEY, tenant_id TEXT);
            CREATE TABLE audit_events (id INTEGER PRIMARY KEY, tenant_id TEXT);
            INSERT INTO tenants VALUES ('expired', '2026-08-01T00:00:00+00:00');
            INSERT INTO audit_events VALUES (1, 'expired');
            """
        )
    return ProbeContext(target_root=tmp_path, database=database)


def test_run_produces_violation_recovery_and_unverifiable_reports(tmp_path):
    promises = [
        promise("P-014", PromiseKind.DELETION_DEADLINE, "customer personal data"),
        promise("P-017", PromiseKind.RETENTION_LIMIT, "database snapshots"),
        promise("P-031", PromiseKind.NOTICE_PERIOD, "subprocessor list"),
    ]

    ledger_run = run_ledger(promises, demo_context(tmp_path))

    reports = {report.promise.id: report for report in ledger_run.reports}
    assert reports["P-014"].verdict is Verdict.VIOLATED
    assert reports["P-017"].verdict is Verdict.HOLDS
    assert reports["P-017"].runs[0].primary.detail == "PermissionError: AccessDenied"
    assert reports["P-017"].runs[0].fallback is not None
    assert reports["P-031"].verdict is Verdict.UNVERIFIABLE
    assert reports["P-031"].probes == []

