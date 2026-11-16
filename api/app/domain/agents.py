from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.domain.models import EvidenceChunk, Transaction


class AgentName(StrEnum):
    RESEARCH = "research"
    ANALYSIS = "analysis"
    COMMUNICATION = "communication"
    VALIDATION = "validation"


class StepStatus(StrEnum):
    OK = "ok"
    ABSTAINED = "abstained"
    SKIPPED = "skipped"
    FAILED = "failed"


class IssueSeverity(StrEnum):
    BLOCKER = "blocker"
    WARNING = "warning"


class ValidationIssue(BaseModel):
    code: str  # ex.: "NUMBER_NOT_SUPPORTED"
    severity: IssueSeverity
    message: str  # pt-BR, mostrável ao usuário


class CalculationResult(BaseModel):
    key: str  # ex.: "net_balance"
    label: str  # pt-BR, ex.: "Saldo líquido"
    value: float | int | str
    unit: str | None = None  # "BRL", "%", "meses"
    source: str  # ex.: "CalculationService.calculate_summary"


class AgentContext(BaseModel):
    question: str
    transactions: list[Transaction] = Field(default_factory=list)
    evidences: list[EvidenceChunk] = Field(default_factory=list)
    abstain_reason: str | None = None
    calculations: list[CalculationResult] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    draft_answer: str | None = None
    model: str | None = None
    issues: list[ValidationIssue] = Field(default_factory=list)
    attempt: int = 0


class AgentStep(BaseModel):
    agent: AgentName
    status: StepStatus
    summary: str  # pt-BR, 1 frase
    duration_ms: int = 0
    detail: dict[str, Any] = Field(default_factory=dict)


class MultiAgentStatus(StrEnum):
    ANSWERED = "answered"
    ABSTAINED = "abstained"
    REJECTED = "rejected"


class MultiAgentResponse(BaseModel):
    query: str
    status: MultiAgentStatus
    answer: str
    model: str | None = None
    evidences: list[EvidenceChunk] = Field(default_factory=list)
    calculations: list[CalculationResult] = Field(default_factory=list)
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
    steps: list[AgentStep] = Field(default_factory=list)
    total_ms: int = 0
