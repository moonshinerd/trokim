"""Seleciona o fluxo de consulta: documento confirmado ou orientação multiagente."""

import re
import time
from collections.abc import Sequence
from datetime import datetime
from zoneinfo import ZoneInfo

from app.domain.agents import (
    AgentContext,
    AgentName,
    AgentStep,
    CalculationResult,
    FinancialFilters,
    MultiAgentResponse,
    MultiAgentStatus,
    StepStatus,
)
from app.domain.models import EvidenceChunk, Transaction, TransactionOrigin, TransactionType
from app.services.agents.orchestrator import REJECTION_MESSAGE, Orchestrator
from app.services.calculation_service import CalculationService
from app.services.financial_chat_resolution import resolve_chat_selection
from app.services.financial_query_service import Clarification
from app.services.library_service import Library
from app.services.statement_profiles import normalize_text

DOCUMENT_ORIGIN = "Lido de foto ou PDF, confirmado por você."


def _select_transactions(
    question: str, transactions: Sequence[Transaction], document_uid: str | None
) -> list[Transaction] | None:
    match = re.fullmatch(r"quanto gastei (?:na|no|em) (.+?)\??", question.strip(), re.I)
    name = match[1] if match else None
    by_name = name is not None
    if re.fullmatch(r"quanto gastei nessa loja\??", question.strip(), re.I):
        reference = next(
            (
                tx
                for tx in transactions
                if tx.uid == document_uid and tx.origin == TransactionOrigin.DOCUMENT
            ),
            None,
        )
        name = (reference.merchant or reference.description) if reference else ""
        by_name = False
    if name is None:
        return None
    normalized = normalize_text(name)
    # Só lançamentos de documento confirmado: o total, a citação e a origem falam da mesma coisa.
    selected = [
        tx
        for tx in transactions
        if normalized
        and tx.origin == TransactionOrigin.DOCUMENT
        and tx.type == TransactionType.DEBIT
        and tx.counts_in_totals
        and normalize_text(tx.merchant or tx.description) == normalized
    ]
    # "Quanto gastei em janeiro/alimentação?" não é de documento: segue para o orquestrador.
    if by_name and not selected:
        return None
    return selected


class AgentQueryService:
    def __init__(self, orchestrator: Orchestrator) -> None:
        self.orchestrator = orchestrator

    async def run(
        self,
        question: str,
        transactions: Sequence[Transaction] = (),
        document_uid: str | None = None,
        library: Library | None = None,
        filters: FinancialFilters | None = None,
    ) -> MultiAgentResponse:
        started = time.perf_counter()
        transactions = library.transactions if library is not None else transactions
        selected = _select_transactions(question, transactions, document_uid)
        if selected is None:
            return await self.orchestrator.run(
                question,
                transactions=transactions,
                library=library,
                filters=filters,
            )
        if filters and any(filters.model_dump().values()):
            snapshot = library or Library(transactions=list(transactions))
            selection = resolve_chat_selection(
                question,
                filters,
                snapshot,
                datetime.now(ZoneInfo("America/Sao_Paulo")).date(),
            )
            reason = None
            if isinstance(selection, Clarification):
                reason = selection.question
            elif len(selection.periods) > 1 or any(p.start is None for p in selection.periods):
                reason = "Para um documento confirmado, use um mês ou intervalo de datas no filtro."
            else:
                allowed = {tx.uid for tx in selection.library.transactions}
                period = selection.periods[0] if selection.periods else None
                selected = [
                    tx
                    for tx in selected
                    if tx.uid in allowed
                    and (period is None or period.start <= tx.date <= period.end)
                ]
                if not selected:
                    reason = (
                        "Não há documento confirmado desse estabelecimento no recorte selecionado."
                    )
            if reason:
                return MultiAgentResponse(
                    query=question,
                    status=MultiAgentStatus.ABSTAINED,
                    answer=reason,
                    steps=[
                        AgentStep(
                            agent=AgentName.ANALYSIS,
                            status=StepStatus.ABSTAINED,
                            summary="Documento ausente ou filtro ambíguo.",
                        )
                    ],
                )
        documents = [tx.uid for tx in selected if tx.origin == TransactionOrigin.DOCUMENT]
        if not documents:
            return MultiAgentResponse(
                query=question,
                status=MultiAgentStatus.ABSTAINED,
                answer="Não identifiquei o documento confirmado dessa loja. "
                "Informe o documento ou o nome do estabelecimento.",
                steps=[
                    AgentStep(
                        agent=AgentName.ANALYSIS,
                        status=StepStatus.ABSTAINED,
                        summary="Documento confirmado não identificado.",
                    )
                ],
                total_ms=max(1, int((time.perf_counter() - started) * 1000)),
            )
        value = CalculationService.calculate_summary(selected).total_expenses
        formatted = f"{value:,.2f}".translate(str.maketrans({",": ".", ".": ","}))
        calculation = CalculationResult(
            key="document_expenses",
            label="Gasto no estabelecimento",
            value=value,
            unit="BRL",
            source="CalculationService.calculate_summary",
        )
        references = ", ".join(documents)
        evidence = EvidenceChunk(
            id="confirmed_documents",
            source_name="Biblioteca local",
            document_title="Lançamentos confirmados",
            section="Origem dos dados",
            content=f"Lançamento(s): {references}. {DOCUMENT_ORIGIN}",
        )
        ctx = AgentContext(
            question=question,
            transactions=selected,
            calculations=[calculation],
            evidences=[evidence],
            draft_answer=f"Gasto no estabelecimento: R$ {formatted}. "
            + f"Lançamento(s): {references}. {DOCUMENT_ORIGIN} [1]",
        )
        steps = [
            AgentStep(
                agent=AgentName.ANALYSIS,
                status=StepStatus.OK,
                summary=DOCUMENT_ORIGIN,
                duration_ms=max(1, int((time.perf_counter() - started) * 1000)),
                detail={
                    "document_uids": documents,
                    "transaction_uids": [tx.uid for tx in selected],
                    "source": calculation.source,
                },
            )
        ]
        validation = await self.orchestrator.validation.run(ctx)
        steps.append(validation)
        approved = validation.status == StepStatus.OK
        return MultiAgentResponse(
            query=question,
            status=MultiAgentStatus.ANSWERED if approved else MultiAgentStatus.REJECTED,
            answer=ctx.draft_answer if approved else REJECTION_MESSAGE,
            calculations=ctx.calculations,
            evidences=ctx.evidences,
            validation_issues=ctx.issues,
            steps=steps,
            total_ms=max(1, int((time.perf_counter() - started) * 1000)),
        )
