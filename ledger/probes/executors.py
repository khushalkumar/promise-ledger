import ast
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import hcl2

from ledger.models import Probe, ProbeOutcome


@dataclass(frozen=True)
class ProbeContext:
    target_root: Path
    database: Path


def execute_probe(probe: Probe, context: ProbeContext) -> tuple[ProbeOutcome, str]:
    if probe.template == "sql.no_rows_after_deadline":
        return _no_rows_after_deadline(probe, context)
    if probe.template == "static.purge_covers_tables":
        return _purge_covers_tables(probe, context)
    if probe.template == "terraform.maximum_retention":
        return _maximum_retention(probe, context)
    if probe.template == "cloud.backup_retention":
        return _cloud_backup_retention(probe)
    raise ValueError(f"unsupported probe template: {probe.template}")


def _no_rows_after_deadline(
    probe: Probe, context: ProbeContext
) -> tuple[ProbeOutcome, str]:
    table = str(probe.params["table"])
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table) is None:
        raise ValueError("unsafe table identifier")

    deadline_days = int(probe.params["deadline_days"])
    cutoff = (datetime.fromisoformat(str(probe.params["now"])) - timedelta(days=deadline_days))
    with sqlite3.connect(context.database) as connection:
        count = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM {table} AS customer_data
            JOIN tenants ON tenants.id = customer_data.tenant_id
            WHERE tenants.terminated_at IS NOT NULL AND tenants.terminated_at <= ?
            """,
            (cutoff.isoformat(),),
        ).fetchone()[0]

    detail = f"{table} has {count} row(s) past the {deadline_days}-day deadline"
    outcome = ProbeOutcome.PASS if count == 0 else ProbeOutcome.FAIL
    return outcome, detail


def _purge_covers_tables(probe: Probe, context: ProbeContext) -> tuple[ProbeOutcome, str]:
    source = _target_path(context.target_root, str(probe.params["path"])).read_text()
    tree = ast.parse(source)
    referenced_tables = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    required_tables = {str(table) for table in probe.params["required_tables"]}
    missing = sorted(required_tables - referenced_tables)
    if missing:
        return ProbeOutcome.FAIL, f"purge omits tenant table(s): {', '.join(missing)}"
    return ProbeOutcome.PASS, "purge covers every required tenant table"


def _maximum_retention(probe: Probe, context: ProbeContext) -> tuple[ProbeOutcome, str]:
    path = _target_path(context.target_root, str(probe.params["path"]))
    with path.open() as terraform:
        configuration = hcl2.load(terraform)
    attribute = str(probe.params.get("attribute", "days"))
    configured_days = int(_find_first(configuration, attribute))
    maximum_days = int(probe.params["maximum_days"])
    detail = (
        f"configured retention is {configured_days} days; contract maximum is {maximum_days}"
    )
    outcome = ProbeOutcome.PASS if configured_days <= maximum_days else ProbeOutcome.FAIL
    return outcome, detail


def _cloud_backup_retention(probe: Probe) -> tuple[ProbeOutcome, str]:
    response = str(probe.params["response"])
    if response == "AccessDenied":
        raise PermissionError(response)
    configured_days = int(probe.params["retention_days"])
    maximum_days = int(probe.params["maximum_days"])
    outcome = ProbeOutcome.PASS if configured_days <= maximum_days else ProbeOutcome.FAIL
    return outcome, f"cloud API reports {configured_days} retention days"


def _target_path(root: Path, relative_path: str) -> Path:
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("probe path escapes target repository")
    return path


def _find_first(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for child in value.values():
            try:
                return _find_first(child, key)
            except KeyError:
                continue
    elif isinstance(value, list):
        for child in value:
            try:
                return _find_first(child, key)
            except KeyError:
                continue
    raise KeyError(key)
