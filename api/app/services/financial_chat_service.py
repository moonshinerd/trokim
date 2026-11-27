"""Executa consultas financeiras a partir de uma seleção validada.

Cada intenção tem um executor explícito. Resolução de filtros e suporte numérico têm
políticas próprias compartilhadas pelos agentes; este módulo não usa LLM nem guarda estado.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date

from app.domain.agents import FinancialFilters, FinancialIntent
from app.domain.models import AccountKind, CounterpartyKind, TransactionCategory
from app.services.financial_chat_resolution import (
    ChatSelection,
    has_period_data,
    resolve_chat_selection,
)
from app.services.financial_query_service import (
    MONTHS,
    STATEMENT_KINDS,
    Clarification,
    Period,
    QueryResult,
    Scope,
)
from app.services.financial_query_service import FinancialQueryService as Queries
from app.services.library_service import Library
from app.services.statement_profiles import normalize_text


def _clarify(question: str) -> QueryResult:
    return QueryResult(clarification=Clarification(question))


def _merchant_query(
    question: str,
    library: Library,
    scope: Scope,
    period: Period | None,
) -> QueryResult | None:
    complement = re.search(r"(?:gastei|gastos?)\s+(?:na|no|em)\s+(.+)", normalize_text(question))
    if complement is None:
        return None
    target = complement[1]
    merchants = {
        tx.merchant
        for tx in library.transactions
        if tx.merchant
        and tx.counterparty_kind != CounterpartyKind.PERSON
        and re.search(rf"\b{re.escape(normalize_text(tx.merchant))}\b", target)
    }
    if merchants:
        if len(merchants) != 1:
            return _clarify("Qual estabelecimento você quer consultar? Informe um por vez.")
        merchant = next(iter(merchants))
        remaining = re.sub(rf"\b{re.escape(normalize_text(merchant))}\b", " ", target)
        if _unknown_target(remaining, scope, library):
            return _clarify(
                "Há um estabelecimento não identificado na pergunta. Informe um por vez."
            )
        source = replace(
            library, transactions=[tx for tx in library.transactions if tx.merchant == merchant]
        )
        result = Queries.totals(source, scope, period)
        result.calculations = [c for c in result.calculations if c.key == "total_expenses"]
        for calculation in result.calculations:
            calculation.label = f"Gasto no estabelecimento {merchant}" + (
                f" em {period.label}" if period else ""
            )
        return result
    return None


def _unknown_target(target: str, scope: Scope, library: Library) -> bool:
    vocabulary = set(MONTHS) | {
        "empresa",
        "pessoal",
        "conta",
        "contas",
        "cartao",
        "cartoes",
        "corrente",
        "mes",
        "cada",
        "todas",
        "todos",
        "ultimos",
        "este",
        "neste",
        "esse",
        "nesse",
        "meu",
        "minha",
        "meses",
        "passado",
        "anterior",
        "atual",
        "ultimo",
        "dias",
        "de",
        "do",
        "da",
        "em",
        "na",
        "no",
        "e",
        "a",
        "ate",
    }
    vocabulary.update(normalize_text(scope.label).split())
    for account in library.accounts.values():
        vocabulary.update(normalize_text(account.institution or "").split())
    return any(
        token not in vocabulary and not token.isdigit() for token in re.findall(r"\w+", target)
    )


@dataclass(frozen=True)
class FinancialQuery:
    question: str
    intent: FinancialIntent
    library: Library
    selection: ChatSelection
    today: date

    @property
    def period(self) -> Period | None:
        return self.selection.periods[0] if self.selection.periods else None


def _period_problem(intent: FinancialIntent, periods: tuple[Period, ...]) -> str | None:
    if intent == FinancialIntent.COMPARISON:
        if len(periods) != 2 or any(period.start is None for period in periods):
            return "Quais dois períodos você quer comparar? Informe o mês e o ano de cada um."
        return None
    if len(periods) > 1:
        return "Há mais de um período. Informe um período, ou peça uma comparação entre dois."
    if intent == FinancialIntent.STATEMENT:
        if not periods or periods[0].kind not in STATEMENT_KINDS:
            return "Você quer a fatura aberta, a fechada ou a próxima fatura?"
    elif intent in {FinancialIntent.INSTALLMENTS, FinancialIntent.COMMITMENTS}:
        if periods and not (
            intent == FinancialIntent.COMMITMENTS and periods[0].kind == "fatura_fechada"
        ):
            return (
                "Parcelas em aberto e dívidas usam a posição dos arquivos importados. "
                "Você quer esse retrato ou os gastos do período?"
            )
    elif periods and periods[0].start is None:
        return (
            "Para essa consulta, informe um mês ou intervalo de datas, em vez de um tipo de fatura."
        )
    return None


def _statement(query: FinancialQuery) -> QueryResult:
    period = query.period
    assert period is not None  # Garantido pela validação da intenção, antes do despacho.
    if period.kind == "proxima_fatura":
        if not any(a.kind == AccountKind.CARD for a in query.selection.library.accounts.values()):
            return QueryResult(
                notes=[
                    "Não há cartão importado nesse recorte. Importe uma fatura para "
                    "consultar a próxima."
                ]
            )
        return Queries.next_statement(query.library, query.today, query.selection.scope)
    return Queries.statement_total(
        query.library, period.kind.removeprefix("fatura_"), query.selection.scope
    )


def _comparison(query: FinancialQuery) -> QueryResult:
    first, second = query.selection.periods
    return Queries.compare_periods(query.library, first, second, query.selection.scope)


def _installments(query: FinancialQuery) -> QueryResult:
    result = Queries.open_installments(query.library, query.selection.scope)
    result.notes.append("O término das parcelas é estimado pelo mês da última parcela vista.")
    return result


def _commitments(query: FinancialQuery) -> QueryResult:
    days = re.search(r"proximos?\s+(\d+)\s+dias", query.question)
    if days and int(days[1]) != 30:
        return _clarify(
            "A consulta de vencimentos cobre os próximos 30 dias. Quer consultar essa janela?"
        )
    result = Queries.commitments(query.library, query.today, query.selection.scope)
    result.notes.append(
        "Pagamentos são associados à última fatura fechada pelos critérios disponíveis no arquivo; "
        "a quitação não é confirmada pelo banco."
    )
    return result


def _spending(query: FinancialQuery) -> QueryResult:
    scope, selected = query.selection.scope, query.selection.library
    merchant_result = _merchant_query(query.question, selected, scope, query.period)
    if merchant_result is not None:
        return merchant_result
    complement = re.search(r"(?:gastei|gastos?)\s+(?:na|no|em)\s+(.+)", query.question)
    if complement and _unknown_target(complement[1], scope, selected):
        return _clarify(
            "Não identifiquei esse estabelecimento nos dados importados. Informe o "
            "nome que aparece no arquivo."
        )
    if query.intent == FinancialIntent.MERCHANTS:
        return Queries.top_merchants(query.library, query.period, scope)
    if complement and not query.period and scope.account_ids is None and scope.owner == "todas":
        return _clarify(
            "Informe a conta, o dono ou o período. Para lojas, peça os maiores "
            "gastos por estabelecimento."
        )
    return Queries.totals(query.library, scope, query.period)


def _categories(query: FinancialQuery) -> QueryResult:
    categories = {
        category
        for category in TransactionCategory
        if re.search(rf"\b{re.escape(normalize_text(category.value))}\b", query.question)
    }
    source = query.library
    if categories:
        source = replace(
            source, transactions=[tx for tx in source.transactions if tx.category in categories]
        )
    return Queries.top_categories(source, query.period, query.selection.scope)


_EXECUTORS: dict[FinancialIntent, Callable[[FinancialQuery], QueryResult]] = {
    FinancialIntent.SUMMARY: _spending,
    FinancialIntent.MERCHANTS: _spending,
    FinancialIntent.CATEGORIES: _categories,
    FinancialIntent.COMPARISON: _comparison,
    FinancialIntent.STATEMENT: _statement,
    FinancialIntent.INSTALLMENTS: _installments,
    FinancialIntent.COMMITMENTS: _commitments,
    FinancialIntent.ACCOUNTS: lambda q: Queries.by_account(q.selection.library, q.period),
    FinancialIntent.TRANSFERS: lambda q: Queries.own_transfers_effect(
        q.library, q.period, q.selection.scope
    ),
}


def query_finances(
    question: str,
    intent: FinancialIntent,
    filters: FinancialFilters,
    library: Library,
    today: date,
) -> QueryResult:
    intent = FinancialIntent(intent)
    selection = resolve_chat_selection(question, filters, library, today)
    if isinstance(selection, Clarification):
        return QueryResult(clarification=selection)
    if selection.scope.account_ids == ():
        return QueryResult(
            notes=[
                f"Não há conta ou fatura importada de {selection.scope.label}. "
                "Importe o arquivo correspondente."
            ]
        )
    if not selection.library.transactions and not selection.library.statements:
        return QueryResult(
            notes=[
                "Não há dados importados para esse recorte. Importe o extrato ou a "
                "fatura da conta e do dono solicitados."
            ]
        )
    if (
        intent == FinancialIntent.SUMMARY
        and selection.periods
        and selection.periods[0].kind in STATEMENT_KINDS
    ):
        intent = FinancialIntent.STATEMENT
    if problem := _period_problem(intent, selection.periods):
        return _clarify(problem)
    for period in selection.periods:
        if not has_period_data(selection.library, period):
            return QueryResult(
                notes=[
                    f"Não há dados importados para {period.label}. "
                    "Importe o extrato ou a fatura desse período."
                ]
            )
    result = _EXECUTORS[intent](
        FinancialQuery(normalize_text(question), intent, library, selection, today)
    )
    if result.calculations:
        result.notes.append(
            "Os valores consideram apenas os arquivos importados; períodos "
            "incompletos podem omitir gastos. "
            "Saldo é a diferença entre receitas e despesas desses lançamentos."
        )
    return result
