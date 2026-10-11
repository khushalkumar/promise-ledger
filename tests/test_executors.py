import json
import sqlite3

import pytest

from ledger.models import Probe, ProbeKind, ProbeOutcome
from ledger.probes.executors import ProbeContext, execute_probe


def make_probe(template: str, params: dict[str, object]) -> Probe:
    return Probe(
        id="probe-1",
        kind=ProbeKind.CONFIG,
        template=template,
        params=params,
        depends_on=[],
    )


def context(tmp_path) -> ProbeContext:
    database = tmp_path / "tasklane.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE tenants (id TEXT PRIMARY KEY, terminated_at TEXT);
            CREATE TABLE audit_events (id INTEGER PRIMARY KEY, tenant_id TEXT);
            INSERT INTO tenants VALUES ('expired', '2026-08-01T00:00:00+00:00');
            INSERT INTO audit_events VALUES (1, 'expired');
            """
        )
    return ProbeContext(target_root=tmp_path, database=database)


def test_data_probe_finds_rows_past_the_deletion_deadline(tmp_path):
    probe = make_probe(
        "sql.no_rows_after_deadline",
        {"table": "audit_events", "deadline_days": 30, "now": "2026-10-11T12:00:00+00:00"},
    )

    outcome, detail = execute_probe(probe, context(tmp_path))

    assert outcome is ProbeOutcome.FAIL
    assert detail == "audit_events has 1 row(s) past the 30-day deadline"


def test_static_probe_reports_a_missing_tenant_table(tmp_path):
    source = tmp_path / "tasklane" / "jobs" / "purge_tenant.py"
    source.parent.mkdir(parents=True)
    source.write_text('for table in ("users", "tasks"):\n    delete(table)\n')
    probe = make_probe(
        "static.purge_covers_tables",
        {
            "path": "tasklane/jobs/purge_tenant.py",
            "required_tables": ["users", "tasks", "audit_events"],
        },
    )

    outcome, detail = execute_probe(probe, context(tmp_path))

    assert outcome is ProbeOutcome.FAIL
    assert detail == "purge omits tenant table(s): audit_events"


def test_terraform_probe_reports_retention_above_contract_limit(tmp_path):
    terraform = tmp_path / "infra" / "storage.tf"
    terraform.parent.mkdir()
    terraform.write_text(
        'resource "aws_s3_bucket_lifecycle_configuration" "backups" {\n'
        '  rule { expiration { days = 90 } }\n'
        '}\n'
    )
    probe = make_probe(
        "terraform.maximum_retention",
        {"path": "infra/storage.tf", "maximum_days": 30},
    )

    outcome, detail = execute_probe(probe, context(tmp_path))

    assert outcome is ProbeOutcome.FAIL
    assert detail == "configured retention is 90 days; contract maximum is 30"


def test_terraform_probe_can_use_rds_retention_as_a_passing_fallback(tmp_path):
    terraform = tmp_path / "infra" / "database.tf"
    terraform.parent.mkdir()
    terraform.write_text(
        'resource "aws_db_instance" "primary" {\n'
        "  backup_retention_period = 30\n"
        "}\n"
    )
    probe = make_probe(
        "terraform.maximum_retention",
        {
            "path": "infra/database.tf",
            "attribute": "backup_retention_period",
            "maximum_days": 30,
        },
    )

    outcome, detail = execute_probe(probe, context(tmp_path))

    assert outcome is ProbeOutcome.PASS
    assert detail == "configured retention is 30 days; contract maximum is 30"


def test_cloud_stub_surfaces_access_denied_as_an_executor_error(tmp_path):
    probe = make_probe("cloud.backup_retention", {"response": "AccessDenied"})

    with pytest.raises(PermissionError, match="AccessDenied"):
        execute_probe(probe, context(tmp_path))


def test_json_probes_check_exact_and_minimum_values(tmp_path):
    config = tmp_path / "config" / "compliance.json"
    config.parent.mkdir()
    config.write_text(
        json.dumps(
            {
                "plans": {"business": {"sso": True}},
                "availability": {"monthly_target_percent": 99.9},
            }
        )
    )
    exact = make_probe(
        "json.value_equals",
        {
            "path": "config/compliance.json",
            "key_path": ["plans", "business", "sso"],
            "expected": True,
        },
    )
    minimum = make_probe(
        "json.value_at_least",
        {
            "path": "config/compliance.json",
            "key_path": ["availability", "monthly_target_percent"],
            "minimum": 99.9,
        },
    )

    probe_context = context(tmp_path)
    assert execute_probe(exact, probe_context)[0] is ProbeOutcome.PASS
    assert execute_probe(minimum, probe_context)[0] is ProbeOutcome.PASS


def test_terraform_region_probe_finds_disallowed_provider(tmp_path):
    terraform = tmp_path / "infra" / "storage.tf"
    terraform.parent.mkdir()
    terraform.write_text(
        'provider "aws" { region = "eu-west-1" }\n'
        'provider "aws" { alias = "exports" region = "us-east-1" }\n'
    )
    probe = make_probe(
        "terraform.allowed_regions",
        {"path": "infra/storage.tf", "allowed_regions": ["eu-west-1"]},
    )

    outcome, detail = execute_probe(probe, context(tmp_path))

    assert outcome is ProbeOutcome.FAIL
    assert detail == "Terraform provider region(s) outside contract: us-east-1"


def test_terraform_attribute_probe_checks_encryption_at_rest(tmp_path):
    terraform = tmp_path / "infra" / "database.tf"
    terraform.parent.mkdir()
    terraform.write_text(
        'resource "aws_db_instance" "primary" {\n  storage_encrypted = true\n}\n'
    )
    probe = make_probe(
        "terraform.attribute_equals",
        {
            "path": "infra/database.tf",
            "attribute": "storage_encrypted",
            "expected": True,
        },
    )

    outcome, detail = execute_probe(probe, context(tmp_path))

    assert outcome is ProbeOutcome.PASS
    assert detail == "storage_encrypted is true; expected true"
