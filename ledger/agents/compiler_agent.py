from __future__ import annotations

import json
from typing import Protocol

import neatlogs
from pydantic import BaseModel, Field

from ledger.agents.compiler import compile_checks
from ledger.models import AssetMap, Probe, Promise


class JsonBackend(Protocol):
    def complete_json(self, system: str, user: str) -> str: ...


class CompilerSelection(BaseModel):
    selected_probe_ids: list[str] = Field(default_factory=list)
    grounding_notes: str


class CompiledChecks(BaseModel):
    probes: list[Probe]
    reasoning: str


SYSTEM_PROMPT = """You are the Promise Ledger check-compiler agent.
Choose from the supplied safe candidate probes; never invent executable code, SQL, paths, or
probe parameters. Every supplied candidate is a required independent check grounded in the
repository inventory and deterministic policy compiler, so select every candidate exactly once.
Explain briefly how the checks cover the written promise. Return JSON only.
"""


@neatlogs.span(kind="AGENT", name="check_compiler_v2")
def compile_checks_with_agent(
    promise: Promise,
    assets: AssetMap,
    backend: JsonBackend,
) -> CompiledChecks:
    candidates = compile_checks(promise, assets)
    request = {
        "promise": promise.model_dump(mode="json"),
        "safe_candidate_probes": [probe.model_dump(mode="json") for probe in candidates],
        "response_schema": CompilerSelection.model_json_schema(),
    }
    selection = CompilerSelection.model_validate_json(
        backend.complete_json(SYSTEM_PROMPT, json.dumps(request, indent=2))
    )

    expected_ids = [probe.id for probe in candidates]
    if selection.selected_probe_ids != expected_ids:
        raise ValueError("compiler agent must select every required safe probe in order")

    return CompiledChecks(probes=candidates, reasoning=selection.grounding_notes)
