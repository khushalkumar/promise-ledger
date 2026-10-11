from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from ledger.models import Promise


def load_registry(path: Path) -> dict[str, str]:
    registry = json.loads(path.read_text())
    if not isinstance(registry, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in registry.items()
    ):
        raise ValueError("Promise id registry must be a JSON object of string keys and values")
    return registry


def assign_canonical_ids(
    promises: Sequence[Promise],
    registry: Mapping[str, str],
) -> list[Promise]:
    deduplicated: dict[str, Promise] = {}
    for promise in promises:
        key = _registry_key(promise)
        if key in deduplicated:
            deduplicated[key] = _merge_same_clause(deduplicated[key], promise)
        else:
            deduplicated[key] = promise

    assigned: list[Promise] = []
    used_ids: set[str] = set()
    for key, promise in deduplicated.items():
        canonical_id = registry.get(key)
        if canonical_id is None:
            raise ValueError(f"No canonical promise id for {key}")
        if canonical_id in used_ids:
            raise ValueError(f"Canonical promise id assigned more than once: {canonical_id}")
        used_ids.add(canonical_id)
        assigned.append(promise.model_copy(update={"id": canonical_id}))
    return assigned


def _merge_same_clause(left: Promise, right: Promise) -> Promise:
    if left.actor != right.actor or left.deadline_days != right.deadline_days:
        raise ValueError(f"Conflicting duplicate extractions for {_registry_key(left)}")
    left_object = left.object.strip()
    right_object = right.object.strip()
    if left_object.lower() in right_object.lower():
        object_name = right_object
    elif right_object.lower() in left_object.lower():
        object_name = left_object
    else:
        object_name = f"{left_object} and {right_object}"
    includes = list(dict.fromkeys([*left.includes, *right.includes]))
    source_text = max([left.source.text, right.source.text], key=len)
    return left.model_copy(
        update={
            "object": object_name,
            "includes": includes,
            "trigger": left.trigger or right.trigger,
            "source": left.source.model_copy(update={"text": source_text}),
        }
    )


def _registry_key(promise: Promise) -> str:
    clause_match = re.match(r"\s*(\d+(?:\.\d+)*)", promise.source.clause)
    clause = clause_match.group(1) if clause_match else promise.source.clause.strip().lower()
    return "|".join([promise.source.document, clause, promise.kind.value])
