from enum import StrEnum

from pydantic import BaseModel


class ProbeOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


class ProbeKind(StrEnum):
    STATIC = "static"
    DATA = "data"
    CONFIG = "config"


class PromiseKind(StrEnum):
    DELETION_DEADLINE = "deletion_deadline"
    RETENTION_LIMIT = "retention_limit"
    DATA_RESIDENCY = "data_residency"
    NOTICE_PERIOD = "notice_period"
    FEATURE_ENTITLEMENT = "feature_entitlement"
    AVAILABILITY_SLO = "availability_slo"
    ENCRYPTION_AT_REST = "encryption_at_rest"
    ADMIN_MFA = "admin_mfa"


class Verdict(StrEnum):
    HOLDS = "holds"
    VIOLATED = "violated"
    AT_RISK = "at_risk"
    UNVERIFIABLE = "unverifiable"


class SourceSpan(BaseModel):
    document: str
    clause: str
    text: str


class Promise(BaseModel):
    id: str
    kind: PromiseKind
    actor: str
    object: str
    includes: list[str] = []
    trigger: str | None = None
    deadline_days: int | None = None
    source: SourceSpan


class AssetMap(BaseModel):
    tenant_tables: list[str]
    source_files: list[str]
    terraform_files: list[str]


class Probe(BaseModel):
    id: str
    kind: ProbeKind
    template: str
    params: dict[str, object]
    depends_on: list[str]
    fallback: "Probe | None" = None


class ProbeResult(BaseModel):
    probe_id: str
    outcome: ProbeOutcome
    evidence_sha256: str
    detail: str
    trace_id: str | None = None


class ProbeRun(BaseModel):
    primary: ProbeResult
    fallback: ProbeResult | None = None

    @property
    def effective_result(self) -> ProbeResult:
        if self.primary.outcome is ProbeOutcome.ERROR and self.fallback is not None:
            return self.fallback
        return self.primary


class PromiseReport(BaseModel):
    promise: Promise
    probes: list[Probe]
    runs: list[ProbeRun]
    verdict: Verdict


class LedgerRun(BaseModel):
    reports: list[PromiseReport]
