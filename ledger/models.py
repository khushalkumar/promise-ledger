from enum import StrEnum

from pydantic import BaseModel


class ProbeOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


class Verdict(StrEnum):
    HOLDS = "holds"
    VIOLATED = "violated"
    AT_RISK = "at_risk"
    UNVERIFIABLE = "unverifiable"


class ProbeResult(BaseModel):
    probe_id: str
    outcome: ProbeOutcome
    evidence_sha256: str
    detail: str
    trace_id: str | None = None

