from sqlalchemy import text

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


def test_create_run_flushes_parent_before_foreign_key_event():
    store = RunStore("sqlite:///:memory:")
    with store.engine.connect() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))

    created = store.create_run("run-fk", target_repository="owner/repository")

    assert created.id == "run-fk"
    assert created.events[0].stage is WorkflowStage.CREATED


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


def test_run_store_persists_and_returns_latest_ledger_result(tmp_path):
    from ledger.models import LedgerRun
    from tests.test_investigator import _violated_report

    store = RunStore(f"sqlite:///{tmp_path / 'state.db'}")
    store.create_run("run-1", target_repository="owner/repository")
    first = LedgerRun(reports=[_violated_report()])
    store.save_ledger_result("run-1", phase="baseline", ledger=first)
    store.save_ledger_result("run-1", phase="final", ledger=first)

    latest = store.latest_ledger_result(phase="final")

    assert latest is not None
    assert latest[0] == "run-1"
    assert latest[1].reports[0].promise.id == "P-014"
    resumed = RunStore(f"sqlite:///{tmp_path / 'state.db'}").ledger_result(
        "run-1", phase="baseline"
    )
    assert resumed is not None
    assert resumed.reports[0].promise.id == "P-014"
