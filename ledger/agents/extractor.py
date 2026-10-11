from __future__ import annotations

import json
from typing import Protocol

import neatlogs
from pydantic import BaseModel, Field, ValidationError

from ledger.documents import LoadedDocument
from ledger.models import Promise, PromiseKind, SourceSpan


class JsonBackend(Protocol):
    def complete_json(self, system: str, user: str) -> str: ...


class ExtractedPromise(BaseModel):
    kind: PromiseKind
    actor: str
    object: str
    includes: list[str] = Field(default_factory=list)
    trigger: str | None = None
    deadline_days: int | None = None
    clause: str
    text: str


class ExtractionBatch(BaseModel):
    promises: list[ExtractedPromise]


SYSTEM_PROMPT = """You extract auditable promises from contracts and policies.
Return JSON only. Extract an item only when the document explicitly commits an actor to an
obligation. Preserve a short exact supporting quote in text and the printed clause identifier.
Do not infer missing deadlines, triggers, locations, or included asset types.
Use a concise, specific noun phrase for object. For example, use "SSO configuration",
"monthly service availability and credits", "customer data", or "administrative accounts"
instead of generic words such as "service" or "requirement".
Use these kinds:
- deletion_deadline: deletion must happen within a deadline after a trigger.
- retention_limit: data, snapshots, or backups must not remain beyond a maximum duration.
- data_residency: data must stay in an explicit location.
- notice_period: notice must precede an event by a stated duration.
- feature_entitlement: a named plan or customer tier includes a feature.
- availability_slo: a quantified service availability commitment.
- encryption_at_rest: an explicit encryption-at-rest commitment.
- admin_mfa: an explicit MFA requirement for administrative accounts.
Classify a separate snapshot or backup maximum as retention_limit even when the same clause also
contains a deletion_deadline.
"""


@neatlogs.span(kind="AGENT", name="promise_extractor")
def extract_promises(
    document: LoadedDocument,
    backend: JsonBackend,
    *,
    starting_index: int = 1,
) -> list[Promise]:
    schema = json.dumps(ExtractionBatch.model_json_schema(), indent=2)
    user_prompt = (
        f"Document: {document.name}\n\n"
        f"Required JSON schema:\n{schema}\n\n"
        f"Document text:\n{document.text}"
    )
    raw = backend.complete_json(SYSTEM_PROMPT, user_prompt)
    batch: ExtractionBatch | None = None
    last_error: json.JSONDecodeError | ValidationError | None = None
    for attempt in range(2):
        try:
            batch = ExtractionBatch.model_validate(json.loads(raw))
            break
        except (json.JSONDecodeError, ValidationError) as error:
            last_error = error
            if attempt == 0:
                raw = backend.complete_json(
                    "Repair the response into valid JSON matching the supplied schema. JSON only.",
                    f"Original request:\n{user_prompt}\n\nInvalid response:\n{raw}",
                )
    if batch is None:
        raise ValueError("Model response was not valid JSON after one repair") from last_error
    return [
        Promise(
            id=f"P-{index:03d}",
            kind=item.kind,
            actor=item.actor,
            object=item.object,
            includes=item.includes,
            trigger=item.trigger,
            deadline_days=item.deadline_days,
            source=SourceSpan(
                document=document.name,
                clause=item.clause,
                text=item.text,
            ),
        )
        for index, item in enumerate(batch.promises, start=starting_index)
    ]
