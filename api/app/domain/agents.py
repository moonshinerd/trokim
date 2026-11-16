from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.domain.models import EvidenceChunk, Transaction


class AgentName(StrEnum):
    RESEARCH = "research"
    ANALYSIS = "analysis"
    COMMUNICATION = "communication"
    VALIDATION = "validation"
    ORCHESTRATOR = "orchestrator"


class AgentStepStatus(StrEnum):
    OK = "ok"
    ABSTAINED = "abstained"
    SKIPPED = "skipped"
    FAILED = "failed"


class IssueSeverity(StrEnum):
    BLOCKER = "blocker"
    WARNING = "warning"


class AgentResponseStatus(StrEnum):
    ANSWERED = "answered"
    ABSTAINED = "abstained"
    REJECTED = "rejected"


class ValidationIssueCode(StrEnum):
    NUMBER_NOT_SUPPORTED = "NUMBER_NOT_SUPPORTED"
    CITATION_INVALID = "CITATION_INVALID"
    OUT_OF_SCOPE_ADVICE = "OUT_OF_SCOPE_ADVICE"
    ABSTENTION_MISMATCH = "ABSTENTION_MISMATCH"
    CALCULATION_MISSING = "CALCULATION_MISSING"


class ValidationIssue(BaseModel):
    code: str
    severity: IssueSeverity = IssueSeverity.BLOCKER
    message: str


class CalculationResult(BaseModel):
    key: str
    label: str
    value: float | int | str
    unit: str = ""
    source: str = ""


class AgentStep(BaseModel):
    agent: AgentName | str
    status: AgentStepStatus
    summary: str
    duration_ms: float = 0.0
    details: dict[str, Any] = Field(default_factory=dict)


class AgentContext(BaseModel):
    query: str
    transactions: list[Transaction] = Field(default_factory=list)
    evidences: list[EvidenceChunk] = Field(default_factory=list)
    abstain_reason: str | None = None
    calculations: list[CalculationResult] = Field(default_factory=list)
    premises: list[str] = Field(default_factory=list)
    draft_answer: str | None = None
    issues: list[ValidationIssue] = Field(default_factory=list)
    attempt: int = 1


class MultiAgentResponse(BaseModel):
    status: AgentResponseStatus
    answer: str
    evidences: list[EvidenceChunk] = Field(default_factory=list)
    calculations: list[CalculationResult] = Field(default_factory=list)
    issues: list[ValidationIssue] = Field(default_factory=list)
    steps: list[AgentStep] = Field(default_factory=list)
