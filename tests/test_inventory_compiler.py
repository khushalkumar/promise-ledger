import sqlite3

from ledger.agents.compiler import compile_checks
from ledger.inventory import build_inventory
from ledger.models import AssetMap, Promise, PromiseKind, SourceSpan
from ledger.probes.executors import ProbeContext


def deletion_promise() -> Promise:
    return Promise(
        id="P-014",
        kind=PromiseKind.DELETION_DEADLINE,
        actor="Tasklane",
        object="customer personal data",
        includes=["backups"],
        trigger="contract.terminated",
        deadline_days=30,
        source=SourceSpan(
            document="Northwind_DPA_v3.pdf",
            clause="7.2",
            text="delete customer personal data, including backups, within 30 days",
        ),
    )


def test_inventory_finds_every_table_with_tenant_data(tmp_path):
    database = tmp_path / "tasklane.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE tenants (id TEXT PRIMARY KEY);
            CREATE TABLE users (id INTEGER PRIMARY KEY, tenant_id TEXT);
            CREATE TABLE audit_events (id INTEGER PRIMARY KEY, tenant_id TEXT);
            CREATE TABLE migrations (version TEXT PRIMARY KEY);
            """
        )
    source = tmp_path / "tasklane" / "jobs" / "purge_tenant.py"
    source.parent.mkdir(parents=True)
    source.write_text("def purge(): pass\n")
    terraform = tmp_path / "infra" / "storage.tf"
    terraform.parent.mkdir()
    terraform.write_text("# storage\n")

    assets = build_inventory(ProbeContext(target_root=tmp_path, database=database))

    assert assets.tenant_tables == ["audit_events", "users"]
    assert assets.source_files == ["tasklane/jobs/purge_tenant.py"]
    assert assets.terraform_files == ["infra/storage.tf"]


def test_compiler_grounds_deletion_promise_to_fixed_probe_templates():
    assets = AssetMap(
        tenant_tables=["audit_events", "users"],
        source_files=["tasklane/jobs/purge_tenant.py"],
        terraform_files=["infra/storage.tf"],
    )

    probes = compile_checks(deletion_promise(), assets)

    assert [probe.template for probe in probes] == [
        "static.purge_covers_tables",
        "sql.no_rows_after_deadline",
        "sql.no_rows_after_deadline",
        "terraform.maximum_retention",
    ]
    assert probes[0].params["required_tables"] == ["audit_events", "users"]
    assert {probe.params.get("table") for probe in probes[1:3]} == {
        "audit_events",
        "users",
    }
    assert all("code" not in probe.params for probe in probes)


def test_compiler_returns_no_probes_when_promise_cannot_be_grounded():
    assets = AssetMap(tenant_tables=[], source_files=[], terraform_files=[])

    assert compile_checks(deletion_promise(), assets) == []


def test_compiler_adds_terraform_fallback_for_snapshot_api_failure():
    promise = Promise(
        id="P-017",
        kind=PromiseKind.RETENTION_LIMIT,
        actor="Tasklane",
        object="database snapshots",
        deadline_days=30,
        source=SourceSpan(
            document="Northwind_DPA_v3.pdf",
            clause="7.2",
            text="backups must be deleted within 30 days",
        ),
    )
    assets = AssetMap(
        tenant_tables=[],
        source_files=[],
        terraform_files=["infra/database.tf"],
    )

    probes = compile_checks(promise, assets)

    assert len(probes) == 1
    assert probes[0].template == "cloud.backup_retention"
    assert probes[0].fallback is not None
    assert probes[0].fallback.template == "terraform.maximum_retention"
    assert probes[0].fallback.params["attribute"] == "backup_retention_period"
