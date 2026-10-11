from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


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


class WorkflowStage(StrEnum):
    CREATED = "created"
    EXTRACTING = "extracting"
    AUDITING = "auditing"
    INVESTIGATING = "investigating"
    REMEDIATING = "remediating"
    PULL_REQUESTS_OPEN = "pull_requests_open"
    RECHECKING = "rechecking"
    COMPLETED = "completed"
    FAILED = "failed"


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


class EntireGraphHit(BaseModel):
    rank: int
    score: float
    file_path: str
    start_line: int
    end_line: int
    symbol_name: str | None = None


class AssetMap(BaseModel):
    tenant_tables: list[str]
    source_files: list[str]
    terraform_files: list[str]
    config_files: list[str] = Field(default_factory=list)
    entire_graph_hits: list[EntireGraphHit] = Field(default_factory=list)


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


class PromiseConflict(BaseModel):
    id: str
    promise_ids: list[str]
    verdict: Verdict
    detail: str


class RunMetrics(BaseModel):
    documents: int
    promises: int
    llm_calls: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class LedgerRun(BaseModel):
    reports: list[PromiseReport]
    conflicts: list[PromiseConflict] = Field(default_factory=list)
    metrics: RunMetrics | None = None
    inventory: AssetMap | None = None


class RootCause(BaseModel):
    id: str
    promise_id: str
    probe_ids: list[str]
    category: str
    file_path: str
    line_start: int | None = None
    summary: str
    fix_goal: str


class RootCauseBatch(BaseModel):
    root_causes: list[RootCause]


class AgentChange(BaseModel):
    changed_files: list[str]
    summary: str
    tests: list[str]
    session_id: str | None = None


class PullRequestRef(BaseModel):
    number: int
    url: str
    branch: str
    commit_sha: str
    created: bool


class RemediationResult(BaseModel):
    root_cause: RootCause
    change: AgentChange | None
    pull_request: PullRequestRef


class WorkflowEvent(BaseModel):
    stage: WorkflowStage
    payload: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WorkflowRun(BaseModel):
    id: str
    target_repository: str
    stage: WorkflowStage
    events: list[WorkflowEvent]


class AutonomousRunResult(BaseModel):
    run_id: str
    baseline: LedgerRun
    root_causes: list[RootCause]
    remediations: list[RemediationResult]
    rechecked: LedgerRun
