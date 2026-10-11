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
    assigned: list[Promise] = []
    used_ids: set[str] = set()
    for promise in promises:
        key = _registry_key(promise)
        canonical_id = registry.get(key)
        if canonical_id is None:
            raise ValueError(f"No canonical promise id for {key}")
        if canonical_id in used_ids:
            raise ValueError(f"Canonical promise id assigned more than once: {canonical_id}")
        used_ids.add(canonical_id)
        assigned.append(promise.model_copy(update={"id": canonical_id}))
    return assigned


def _registry_key(promise: Promise) -> str:
    clause_match = re.match(r"\s*(\d+(?:\.\d+)*)", promise.source.clause)
    clause = clause_match.group(1) if clause_match else promise.source.clause.strip().lower()
    return "|".join([promise.source.document, clause, promise.kind.value])
