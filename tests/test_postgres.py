import os

import pytest
from sqlalchemy import text

from ledger.database import create_database_engine
from ledger.models import PromiseKind, Verdict
from ledger.orchestrator import run_ledger
from ledger.probes.executors import ProbeContext
from tests.test_orchestrator import promise


@pytest.mark.skipif(
    not os.getenv("PROMISE_LEDGER_TEST_POSTGRES_URL"),
    reason="PROMISE_LEDGER_TEST_POSTGRES_URL is not configured",
)
def test_postgres_inventory_and_data_probe(tmp_path):
    database_url = os.environ["PROMISE_LEDGER_TEST_POSTGRES_URL"]
    engine = create_database_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        connection.execute(
            text(
                """
                CREATE TABLE tenants (
                    id TEXT PRIMARY KEY,
                    terminated_at TIMESTAMPTZ
                );
                CREATE TABLE audit_events (
                    id INTEGER PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id)
                );
                INSERT INTO tenants VALUES ('expired', '2026-08-01T00:00:00+00:00');
                INSERT INTO audit_events VALUES (1, 'expired');
                """
            )
        )

    source = tmp_path / "tasklane" / "jobs" / "purge_tenant.py"
    source.parent.mkdir(parents=True)
    source.write_text('for table in ("audit_events",):\n    delete(table)\n')
    infra = tmp_path / "infra"
    infra.mkdir()
    (infra / "storage.tf").write_text(
        'resource "aws_s3_bucket_lifecycle_configuration" "backups" {\n'
        "  rule { expiration { days = 30 } }\n"
        "}\n"
    )

    result = run_ledger(
        [promise("P-014", PromiseKind.DELETION_DEADLINE, "customer personal data")],
        ProbeContext(target_root=tmp_path, database=database_url),
    )

    assert result.inventory is not None
    assert result.inventory.tenant_tables == ["audit_events"]
    assert result.reports[0].verdict is Verdict.VIOLATED
    assert result.reports[0].runs[1].primary.detail.startswith("audit_events has 1 row")
