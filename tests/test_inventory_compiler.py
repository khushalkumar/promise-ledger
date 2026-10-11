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
    config = tmp_path / "config" / "compliance.json"
    config.parent.mkdir()
    config.write_text("{}\n")

    assets = build_inventory(ProbeContext(target_root=tmp_path, database=database))

    assert assets.tenant_tables == ["audit_events", "users"]
    assert assets.source_files == ["tasklane/jobs/purge_tenant.py"]
    assert assets.terraform_files == ["infra/storage.tf"]
    assert assets.config_files == ["config/compliance.json"]


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


def test_compiler_grounds_policy_backup_retention_to_storage_lifecycle():
    promise = Promise(
        id="P-044",
        kind=PromiseKind.RETENTION_LIMIT,
        actor="Tasklane",
        object="customer personal data and backups",
        includes=["backups"],
        deadline_days=90,
        source=SourceSpan(
            document="privacy_policy.md",
            clause="5",
            text="retain customer personal data and backups for up to 90 days",
        ),
    )
    assets = AssetMap(
        tenant_tables=[],
        source_files=[],
        terraform_files=["infra/database.tf", "infra/storage.tf"],
    )

    probes = compile_checks(promise, assets)

    assert len(probes) == 1
    assert probes[0].template == "terraform.maximum_retention"
    assert probes[0].params == {"path": "infra/storage.tf", "maximum_days": 90}


def test_compiler_grounds_data_residency_to_provider_regions():
    promise = Promise(
        id="P-021",
        kind=PromiseKind.DATA_RESIDENCY,
        actor="Tasklane",
        object="European customer personal data",
        source=SourceSpan(
            document="Northwind_DPA_v3.pdf",
            clause="9.1",
            text="stored and processed only in eu-west-1",
        ),
    )
    assets = AssetMap(
        tenant_tables=[],
        source_files=[],
        terraform_files=["infra/storage.tf"],
    )

    probes = compile_checks(promise, assets)

    assert len(probes) == 1
    assert probes[0].template == "terraform.allowed_regions"
    assert probes[0].params["allowed_regions"] == ["eu-west-1"]


def test_compiler_grounds_msa_promises_to_fixed_config_checks():
    assets = AssetMap(
        tenant_tables=[],
        source_files=[],
        terraform_files=["infra/database.tf"],
        config_files=["config/compliance.json"],
    )
    promises = [
        Promise(
            id="P-040",
            kind=PromiseKind.FEATURE_ENTITLEMENT,
            actor="Tasklane",
            object="SSO configuration",
            source=SourceSpan(document="msa.pdf", clause="4.1", text="Business includes SSO"),
        ),
        Promise(
            id="P-041",
            kind=PromiseKind.AVAILABILITY_SLO,
            actor="Tasklane",
            object="99.9% monthly availability",
            source=SourceSpan(document="msa.pdf", clause="6.2", text="99.9% availability"),
        ),
        Promise(
            id="P-042",
            kind=PromiseKind.ENCRYPTION_AT_REST,
            actor="Tasklane",
            object="customer data",
            source=SourceSpan(document="msa.pdf", clause="8.1", text="encrypt at rest"),
        ),
        Promise(
            id="P-043",
            kind=PromiseKind.ADMIN_MFA,
            actor="Tasklane",
            object="administrative accounts",
            source=SourceSpan(document="msa.pdf", clause="8.1", text="require MFA"),
        ),
    ]

    templates = [[probe.template for probe in compile_checks(item, assets)] for item in promises]

    assert templates == [
        ["json.value_equals"],
        ["json.value_at_least", "json.value_equals"],
        ["terraform.attribute_equals"],
        ["json.value_equals"],
    ]
