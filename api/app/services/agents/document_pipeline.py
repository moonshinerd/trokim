"""Extração de documento como passo do orquestrador (#96).

Roda o agente de documento (#88) e, em seguida, a validação (#89) contra a biblioteca da sessão,
devolvendo uma trilha de passos com duração e motor usado, para o app mostrar "como li este
documento". O conteúdo do arquivo só existe em memória e é zerado pelo agente ao terminar.
"""

import time

from app.domain.agents import (
    AgentName,
    AgentStep,
    IssueSeverity,
    StepStatus,
    ValidationIssue,
)
from app.domain.documents import DocumentExtractResponse, ExtractedDocument
from app.services.agents.document import DocumentAgent, DocumentContext
from app.services.document_adapter import from_agent_document
from app.services.document_validation import validate_document
from app.services.library_service import Library


class DocumentFailure(Exception):
    """Falha técnica de leitura; ``code`` é seguro para mostrar (nunca traz erro bruto)."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _merge(*groups: list[ValidationIssue]) -> list[ValidationIssue]:
    seen: set[tuple[str, str]] = set()
    merged: list[ValidationIssue] = []
    for issue in (i for group in groups for i in group):
        key = (issue.code, issue.message)
        if key not in seen:
            seen.add(key)
            merged.append(issue)
    return merged


class DocumentPipeline:
    def __init__(self, agent: DocumentAgent) -> None:
        self.agent = agent

    async def run(
        self,
        content: bytes,
        media_type: str,
        library: Library | None = None,
        account_id: str | None = None,
    ) -> DocumentExtractResponse:
        started = time.perf_counter()
        ctx = DocumentContext(content=content, media_type=media_type)  # type: ignore[arg-type]
        step = await self.agent.run(ctx)
        steps = [step]
        document: ExtractedDocument | None = ctx.result
        if step.status == StepStatus.FAILED or document is None:
            raise DocumentFailure(str(step.detail.get("code", "DOCUMENT_PROCESSING_FAILED")))

        issues = list(document.issues)
        if not document.abstained:
            t0 = time.perf_counter()
            review = from_agent_document(document)
            review.account_id = account_id
            found = validate_document(review, library)
            issues = _merge(issues, found)
            blockers = sum(1 for i in issues if i.severity == IssueSeverity.BLOCKER)
            steps.append(
                AgentStep(
                    agent=AgentName.VALIDATION,
                    status=StepStatus.FAILED if blockers else StepStatus.OK,
                    summary=f"Validação do documento: {blockers} bloqueio(s), "
                    f"{len(issues) - blockers} aviso(s).",
                    duration_ms=max(1, int((time.perf_counter() - t0) * 1000)),
                    detail={"issues": [i.code for i in issues]},
                )
            )
        can_confirm = not document.abstained and not any(
            i.severity == IssueSeverity.BLOCKER for i in issues
        )
        return DocumentExtractResponse(
            document=document,
            validation_issues=issues,
            can_confirm=can_confirm,
            steps=steps,
            total_ms=max(1, int((time.perf_counter() - started) * 1000)),
        )
