from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pydantic import ValidationError

from ledger.models import EntireGraphHit


def search_entire_graph(
    repository: Path, query: str, *, timeout_seconds: int = 10
) -> list[EntireGraphHit]:
    command = [
        "entire",
        "graph",
        "search",
        "--repo",
        str(repository.resolve()),
        "--profile",
        "full",
        "--format",
        "json",
        "--top-k",
        "10",
        "--query",
        query,
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if result.returncode != 0:
            return []
        payload = json.loads(result.stdout)
        return [EntireGraphHit.model_validate(item) for item in payload.get("results", [])]
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, ValidationError):
        return []
