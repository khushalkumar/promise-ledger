import ast
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import hcl2
from sqlalchemy import text

from ledger.database import create_database_engine, database_url
from ledger.models import Probe, ProbeOutcome
from ledger.probes.runner import ProbeExecution


@dataclass(frozen=True)
class ProbeContext:
    target_root: Path
    database: str | Path


def execute_probe(probe: Probe, context: ProbeContext) -> ProbeExecution:
    result: tuple[ProbeOutcome, str]
    if probe.template == "sql.no_rows_after_deadline":
        result = _no_rows_after_deadline(probe, context)
    elif probe.template == "static.purge_covers_tables":
        result = _purge_covers_tables(probe, context)
    elif probe.template == "terraform.maximum_retention":
        result = _maximum_retention(probe, context)
    elif probe.template == "terraform.allowed_regions":
        result = _allowed_regions(probe, context)
    elif probe.template == "terraform.attribute_equals":
        result = _terraform_attribute_equals(probe, context)
    elif probe.template == "json.value_equals":
        result = _json_value_equals(probe, context)
    elif probe.template == "json.value_at_least":
        result = _json_value_at_least(probe, context)
    elif probe.template == "cloud.backup_retention":
        result = _cloud_backup_retention(probe)
    else:
        raise ValueError(f"unsupported probe template: {probe.template}")
    outcome, detail = result
    return ProbeExecution(
        outcome=outcome,
        detail=detail,
        evidence_material=_evidence_material(probe, context, detail),
    )


def _evidence_material(probe: Probe, context: ProbeContext, detail: str) -> bytes:
    material = [
        json.dumps(probe.model_dump(mode="json"), sort_keys=True).encode(),
        detail.encode(),
    ]
    relative_path = probe.params.get("path")
    if isinstance(relative_path, str):
        material.append(_target_path(context.target_root, relative_path).read_bytes())
    return b"\0".join(material)


def _no_rows_after_deadline(
    probe: Probe, context: ProbeContext
) -> tuple[ProbeOutcome, str]:
    table = str(probe.params["table"])
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table) is None:
        raise ValueError("unsafe table identifier")

    deadline_days = int(probe.params["deadline_days"])
    cutoff = (datetime.fromisoformat(str(probe.params["now"])) - timedelta(days=deadline_days))
    cutoff_value = (
        cutoff
        if database_url(context.database).startswith("postgresql")
        else cutoff.isoformat()
    )
    engine = create_database_engine(context.database)
    with engine.connect() as connection:
        count = connection.scalar(
            text(
                f"""
            SELECT COUNT(*)
            FROM {table} AS customer_data
            JOIN tenants ON tenants.id = customer_data.tenant_id
            WHERE tenants.terminated_at IS NOT NULL AND tenants.terminated_at <= :cutoff
            """,
            ),
            {"cutoff": cutoff_value},
        )

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
    referenced_tables.update(_imported_tenant_registry_tables(tree, context.target_root))
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
    configured_value = _find_first(configuration, attribute)
    configured_days, capped = _resolve_retention_days(configuration, configured_value)
    maximum_days = int(probe.params["maximum_days"])
    qualifier = "is capped at" if capped else "is"
    detail = (
        f"configured retention {qualifier} {configured_days} days; "
        f"contract maximum is {maximum_days}"
    )
    outcome = ProbeOutcome.PASS if configured_days <= maximum_days else ProbeOutcome.FAIL
    return outcome, detail


def _imported_tenant_registry_tables(tree: ast.AST, target_root: Path) -> set[str]:
    imported: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        for alias in node.names:
            if alias.name == "TENANT_TABLES":
                imported.append((node.module, alias.asname or alias.name))
    used_names = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }
    tables: set[str] = set()
    for module, local_name in imported:
        if local_name not in used_names or not _iterates_entire_registry(tree, local_name):
            continue
        module_path = _target_path(target_root, module.replace(".", "/") + ".py")
        module_tree = ast.parse(module_path.read_text())
        table_symbols: dict[str, str] = {}
        registry_value: ast.AST | None = None
        for node in module_tree.body:
            if not isinstance(node, ast.Assign):
                continue
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if "TENANT_TABLES" in names:
                registry_value = node.value
            if (
                len(names) == 1
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "Table"
                and node.value.args
                and isinstance(node.value.args[0], ast.Constant)
                and isinstance(node.value.args[0].value, str)
            ):
                table_symbols[names[0]] = node.value.args[0].value
        if registry_value is not None:
            registry_symbols = {
                node.id for node in ast.walk(registry_value) if isinstance(node, ast.Name)
            }
            tables.update(
                table_name
                for symbol, table_name in table_symbols.items()
                if symbol in registry_symbols
            )
    return tables


def _iterates_entire_registry(tree: ast.AST, name: str) -> bool:
    direct_iteration = any(
        isinstance(node, ast.For)
        and isinstance(node.iter, ast.Call)
        and not node.iter.args
        and not node.iter.keywords
        and isinstance(node.iter.func, ast.Attribute)
        and node.iter.func.attr == "values"
        and isinstance(node.iter.func.value, ast.Name)
        and node.iter.func.value.id == name
        for node in ast.walk(tree)
    )
    if direct_iteration:
        return True

    registry_sets = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "set"
        and len(node.value.args) == 1
        and not node.value.keywords
        and _is_registry_values_call(node.value.args[0], name)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    deletion_plans = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and _is_complete_registry_filter(node.value, registry_sets)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    return any(
        isinstance(node, ast.For)
        and isinstance(node.iter, ast.Name)
        and node.iter.id in deletion_plans
        for node in ast.walk(tree)
    )


def _is_registry_values_call(node: ast.AST, name: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and not node.args
        and not node.keywords
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "values"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == name
    )


def _is_complete_registry_filter(node: ast.AST, registry_sets: set[str]) -> bool:
    if not isinstance(node, ast.GeneratorExp) or len(node.generators) != 1:
        return False
    generator = node.generators[0]
    if not isinstance(generator.target, ast.Name) or len(generator.ifs) != 1:
        return False
    item_name = generator.target.id
    condition = generator.ifs[0]
    return (
        isinstance(node.elt, ast.Name)
        and node.elt.id == item_name
        and isinstance(condition, ast.Compare)
        and isinstance(condition.left, ast.Name)
        and condition.left.id == item_name
        and len(condition.ops) == 1
        and isinstance(condition.ops[0], ast.In)
        and len(condition.comparators) == 1
        and isinstance(condition.comparators[0], ast.Name)
        and condition.comparators[0].id in registry_sets
    )


def _resolve_retention_days(
    configuration: dict[str, Any], configured_value: object
) -> tuple[int, bool]:
    if isinstance(configured_value, int | float):
        return int(configured_value), False
    if not isinstance(configured_value, str):
        raise ValueError("retention value is not numeric")
    match = re.fullmatch(r"\$\{var\.([A-Za-z_][A-Za-z0-9_]*)\}", configured_value)
    if match is None:
        raise ValueError(f"retention value is not a supported variable: {configured_value}")
    variable_name = match.group(1)
    variable = next(
        (
            item[variable_name]
            for item in configuration.get("variable", [])
            if variable_name in item
        ),
        None,
    )
    if not isinstance(variable, dict):
        raise ValueError(f"Terraform variable is not defined: {variable_name}")
    upper_bounds = [
        int(bound)
        for validation in variable.get("validation", [])
        for bound in re.findall(
            rf"\bvar\.{re.escape(variable_name)}\s*<=\s*(\d+)\b",
            str(validation.get("condition", "")),
        )
    ]
    if not upper_bounds:
        raise ValueError(f"Terraform variable has no provable maximum: {variable_name}")
    configured_maximum = min(upper_bounds)
    default = variable.get("default")
    if isinstance(default, int | float) and int(default) > configured_maximum:
        raise ValueError(f"Terraform variable default exceeds its maximum: {variable_name}")
    return configured_maximum, True


def _allowed_regions(probe: Probe, context: ProbeContext) -> tuple[ProbeOutcome, str]:
    path = _target_path(context.target_root, str(probe.params["path"]))
    with path.open() as terraform:
        configuration = hcl2.load(terraform)
    allowed = {str(region) for region in probe.params["allowed_regions"]}
    configured = {
        str(provider["aws"]["region"])
        for provider in configuration.get("provider", [])
        if "aws" in provider and "region" in provider["aws"]
    }
    outside = sorted(configured - allowed)
    if outside:
        return (
            ProbeOutcome.FAIL,
            f"Terraform provider region(s) outside contract: {', '.join(outside)}",
        )
    detail = f"all Terraform provider regions are allowed: {', '.join(sorted(allowed))}"
    return ProbeOutcome.PASS, detail


def _terraform_attribute_equals(
    probe: Probe, context: ProbeContext
) -> tuple[ProbeOutcome, str]:
    path = _target_path(context.target_root, str(probe.params["path"]))
    with path.open() as terraform:
        configuration = hcl2.load(terraform)
    attribute = str(probe.params["attribute"])
    actual = _find_first(configuration, attribute)
    expected = probe.params["expected"]
    outcome = ProbeOutcome.PASS if actual == expected else ProbeOutcome.FAIL
    return outcome, f"{attribute} is {_format_value(actual)}; expected {_format_value(expected)}"


def _json_value_equals(probe: Probe, context: ProbeContext) -> tuple[ProbeOutcome, str]:
    actual = _json_value(probe, context)
    expected = probe.params["expected"]
    key = ".".join(str(part) for part in probe.params["key_path"])
    outcome = ProbeOutcome.PASS if actual == expected else ProbeOutcome.FAIL
    return outcome, f"{key} is {_format_value(actual)}; expected {_format_value(expected)}"


def _json_value_at_least(probe: Probe, context: ProbeContext) -> tuple[ProbeOutcome, str]:
    actual = float(_json_value(probe, context))
    minimum = float(probe.params["minimum"])
    key = ".".join(str(part) for part in probe.params["key_path"])
    outcome = ProbeOutcome.PASS if actual >= minimum else ProbeOutcome.FAIL
    return outcome, f"{key} is {actual:g}; minimum is {minimum:g}"


def _json_value(probe: Probe, context: ProbeContext) -> Any:
    path = _target_path(context.target_root, str(probe.params["path"]))
    value: Any = json.loads(path.read_text())
    for key in probe.params["key_path"]:
        if not isinstance(value, dict):
            raise KeyError(str(key))
        value = value[str(key)]
    return value


def _format_value(value: object) -> str:
    return json.dumps(value, sort_keys=True)


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
