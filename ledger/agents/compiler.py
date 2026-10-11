from datetime import UTC, datetime

from ledger.models import AssetMap, Probe, ProbeKind, Promise, PromiseKind


def compile_checks(promise: Promise, assets: AssetMap) -> list[Probe]:
    if promise.kind is PromiseKind.RETENTION_LIMIT:
        database_files = [
            path for path in assets.terraform_files if path.endswith("database.tf")
        ]
        if not database_files:
            return []
        maximum_days = promise.deadline_days or 30
        fallback = Probe(
            id=f"{promise.id}-terraform-fallback",
            kind=ProbeKind.CONFIG,
            template="terraform.maximum_retention",
            params={
                "path": database_files[0],
                "attribute": "backup_retention_period",
                "maximum_days": maximum_days,
            },
            depends_on=[database_files[0]],
        )
        return [
            Probe(
                id=f"{promise.id}-cloud-snapshots",
                kind=ProbeKind.CONFIG,
                template="cloud.backup_retention",
                params={
                    "response": "AccessDenied",
                    "maximum_days": maximum_days,
                },
                depends_on=["aws:rds:tasklane-primary"],
                fallback=fallback,
            )
        ]

    if promise.kind is not PromiseKind.DELETION_DEADLINE or not assets.tenant_tables:
        return []

    deadline_days = promise.deadline_days or 30
    probes: list[Probe] = []
    purge_sources = [path for path in assets.source_files if path.endswith("purge_tenant.py")]
    if purge_sources:
        probes.append(
            Probe(
                id=f"{promise.id}-static-purge",
                kind=ProbeKind.STATIC,
                template="static.purge_covers_tables",
                params={
                    "path": purge_sources[0],
                    "required_tables": assets.tenant_tables,
                },
                depends_on=[purge_sources[0], *assets.tenant_tables],
            )
        )

    compiled_at = datetime.now(UTC).isoformat()
    probes.extend(
        Probe(
            id=f"{promise.id}-data-{table}",
            kind=ProbeKind.DATA,
            template="sql.no_rows_after_deadline",
            params={"table": table, "deadline_days": deadline_days, "now": compiled_at},
            depends_on=[table, "tenants"],
        )
        for table in assets.tenant_tables
    )

    storage_files = [path for path in assets.terraform_files if path.endswith("storage.tf")]
    if "backups" in promise.includes and storage_files:
        probes.append(
            Probe(
                id=f"{promise.id}-config-backups",
                kind=ProbeKind.CONFIG,
                template="terraform.maximum_retention",
                params={"path": storage_files[0], "maximum_days": deadline_days},
                depends_on=[storage_files[0]],
            )
        )
    return probes
