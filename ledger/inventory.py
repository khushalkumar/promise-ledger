import sqlite3

from ledger.models import AssetMap
from ledger.probes.executors import ProbeContext


def build_inventory(context: ProbeContext) -> AssetMap:
    with sqlite3.connect(context.database) as connection:
        table_names = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
        ]
        tenant_tables = [
            table
            for table in table_names
            if any(
                column[1] == "tenant_id"
                for column in connection.execute(f'PRAGMA table_info("{table}")')
            )
        ]

    source_root = context.target_root / "tasklane"
    source_files = sorted(
        str(path.relative_to(context.target_root)) for path in source_root.rglob("*.py")
    )
    terraform_files = sorted(
        str(path.relative_to(context.target_root))
        for path in (context.target_root / "infra").glob("*.tf")
    )
    return AssetMap(
        tenant_tables=tenant_tables,
        source_files=source_files,
        terraform_files=terraform_files,
    )
