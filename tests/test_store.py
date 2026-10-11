from ledger.models import WorkflowStage
from ledger.store import RunStore


def test_run_store_persists_stage_history_and_can_resume(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'ledger-state.db'}"
    store = RunStore(database_url)

    store.create_run("run-123", target_repository="khushalkumar/tasklane-demo")
    store.record_stage("run-123", WorkflowStage.AUDITING, {"promises": 9})
    store.record_stage("run-123", WorkflowStage.INVESTIGATING, {"violations": ["P-014"]})

    resumed = RunStore(database_url).get_run("run-123")

    assert resumed is not None
    assert resumed.stage is WorkflowStage.INVESTIGATING
    assert [event.stage for event in resumed.events] == [
        WorkflowStage.CREATED,
        WorkflowStage.AUDITING,
        WorkflowStage.INVESTIGATING,
    ]
    assert resumed.events[-1].payload == {"violations": ["P-014"]}


def test_run_store_records_probe_dependencies_for_selective_recheck(tmp_path):
    store = RunStore(f"sqlite:///{tmp_path / 'ledger-state.db'}")
    store.create_run("run-123", target_repository="khushalkumar/tasklane-demo")
    store.replace_probe_dependencies(
        "run-123",
        {
            "P-014-static-purge": ["tasklane/jobs/purge_tenant.py", "audit_events"],
            "P-014-config-backups": ["infra/storage.tf"],
            "P-021-terraform-regions": ["infra/storage.tf"],
        },
    )

    affected = store.affected_probe_ids(
        "run-123", ["tasklane/jobs/purge_tenant.py", "infra/storage.tf"]
    )

    assert affected == [
        "P-014-config-backups",
        "P-014-static-purge",
        "P-021-terraform-regions",
    ]


def test_run_store_creates_parent_directory_for_fresh_sqlite_database(tmp_path):
    database = tmp_path / "fresh" / "nested" / "state.db"

    store = RunStore(f"sqlite:///{database}")

    assert database.exists()
    store.create_run("run-fresh", target_repository="owner/repository")
