import re
from datetime import UTC, datetime

import neatlogs

from ledger.models import AssetMap, Probe, ProbeKind, Promise, PromiseKind


@neatlogs.span(kind="AGENT", name="check_compiler")
def compile_checks(promise: Promise, assets: AssetMap) -> list[Probe]:
    if promise.kind is PromiseKind.DATA_RESIDENCY:
        storage_files = [path for path in assets.terraform_files if path.endswith("storage.tf")]
        regions = sorted(set(re.findall(r"\b[a-z]{2}-[a-z]+-\d\b", promise.source.text)))
        if not storage_files or not regions:
            return []
        return [
            Probe(
                id=f"{promise.id}-terraform-regions",
                kind=ProbeKind.CONFIG,
                template="terraform.allowed_regions",
                params={"path": storage_files[0], "allowed_regions": regions},
                depends_on=[storage_files[0]],
            )
        ]

    compliance_files = [
        path for path in assets.config_files if path.endswith("compliance.json")
    ]
    if promise.kind is PromiseKind.FEATURE_ENTITLEMENT:
        if not compliance_files:
            return []
        return [
            _json_probe(
                promise,
                compliance_files[0],
                "plans.business.sso",
                ["plans", "business", "sso"],
                True,
            )
        ]

    if promise.kind is PromiseKind.AVAILABILITY_SLO:
        percentages = re.findall(r"\b\d{2,3}(?:\.\d+)?(?=%)", promise.source.text)
        if not compliance_files or not percentages:
            return []
        path = compliance_files[0]
        return [
            Probe(
                id=f"{promise.id}-availability-target",
                kind=ProbeKind.CONFIG,
                template="json.value_at_least",
                params={
                    "path": path,
                    "key_path": ["availability", "monthly_target_percent"],
                    "minimum": float(percentages[0]),
                },
                depends_on=[path],
            ),
            _json_probe(
                promise,
                path,
                "availability.service_credits",
                ["availability", "service_credits"],
                True,
            ),
        ]

    if promise.kind is PromiseKind.ENCRYPTION_AT_REST:
        database_files = [
            path for path in assets.terraform_files if path.endswith("database.tf")
        ]
        if not database_files:
            return []
        path = database_files[0]
        return [
            Probe(
                id=f"{promise.id}-storage-encryption",
                kind=ProbeKind.CONFIG,
                template="terraform.attribute_equals",
                params={"path": path, "attribute": "storage_encrypted", "expected": True},
                depends_on=[path],
            )
        ]

    if promise.kind is PromiseKind.ADMIN_MFA:
        if not compliance_files:
            return []
        return [
            _json_probe(
                promise,
                compliance_files[0],
                "security.admin_mfa_required",
                ["security", "admin_mfa_required"],
                True,
            )
        ]

    if promise.kind is PromiseKind.RETENTION_LIMIT:
        storage_files = [path for path in assets.terraform_files if path.endswith("storage.tf")]
        maximum_days = promise.deadline_days or 30
        if "snapshot" not in promise.object.lower() and storage_files:
            path = storage_files[0]
            return [
                Probe(
                    id=f"{promise.id}-storage-retention",
                    kind=ProbeKind.CONFIG,
                    template="terraform.maximum_retention",
                    params={"path": path, "maximum_days": maximum_days},
                    depends_on=[path],
                )
            ]
        database_files = [
            path for path in assets.terraform_files if path.endswith("database.tf")
        ]
        if not database_files:
            return []
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


def _json_probe(
    promise: Promise,
    path: str,
    suffix: str,
    key_path: list[str],
    expected: object,
) -> Probe:
    return Probe(
        id=f"{promise.id}-{suffix.replace('.', '-')}",
        kind=ProbeKind.CONFIG,
        template="json.value_equals",
        params={"path": path, "key_path": key_path, "expected": expected},
        depends_on=[path],
    )
