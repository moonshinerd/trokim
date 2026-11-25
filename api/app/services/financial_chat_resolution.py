"""Resolve uma seleção de conta, dono e período para os dois fluxos do chat."""

import calendar
import re
from dataclasses import dataclass, replace
from datetime import date

from app.domain.agents import FinancialFilters
from app.services.financial_query_service import (
    MONTHS,
    Clarification,
    Period,
    Scope,
    account_name,
)
from app.services.financial_query_service import FinancialQueryService as Queries
from app.services.library_service import Library
from app.services.statement_profiles import normalize_text


def resolve_chat_scope(
    question: str, filters: FinancialFilters, library: Library
) -> Scope | Clarification:
    # Um id explícito desambigua cartões do mesmo banco antes da resolução textual.
    candidates = library
    if filters.account_id:
        if filters.account_id not in library.accounts:
            return Clarification(
                "A conta selecionada não foi importada. Importe o extrato dessa conta."
            )
        candidates = replace(
            library, accounts={filters.account_id: library.accounts[filters.account_id]}
        )
    if filters.owner and filters.owner != "todas":
        candidates = replace(
            candidates,
            accounts={
                aid: account
                for aid, account in candidates.accounts.items()
                if account.owner == filters.owner
            },
        )
    scope = Queries.resolve_scope(question, candidates)
    if isinstance(scope, Clarification):
        return scope
    if filters.owner and scope.owner != "todas" and scope.owner != filters.owner:
        return Clarification(
            "O dono selecionado e o informado na pergunta são diferentes. Qual devo usar?"
        )
    owner = filters.owner or scope.owner
    ids = scope.account_ids
    if filters.account_id:
        if ids is not None and filters.account_id not in ids:
            return Clarification(
                "A conta selecionada não combina com a pergunta. Qual conta devo usar?"
            )
        ids = (filters.account_id,)
    label = scope.label
    if ids and len(ids) == 1:
        label = account_name(library.accounts[ids[0]])
    elif filters.owner:
        label = owner
    return Scope(ids, owner, label)


def resolve_chat_periods(
    question: str,
    filters: FinancialFilters,
    library: Library,
    today: date,
) -> list[Period] | Clarification:
    if re.search(r"\b(semana|ontem|amanha|semestre|trimestre)\b", normalize_text(question)):
        return Clarification("Informe o período como mês e ano ou intervalo de datas completo.")
    try:
        periods = Queries.resolve_periods(question, library, today)
    except (ValueError, OverflowError):
        return Clarification("As datas informadas são inválidas. Informe o mês e o ano novamente.")
    if isinstance(periods, Clarification) and not filters.period:
        return periods
    if filters.period:
        value = filters.period
        if re.fullmatch(r"\d{4}-\d{2}", value):
            try:
                first = date.fromisoformat(value + "-01")
            except ValueError:
                return Clarification("O mês selecionado é inválido. Informe AAAA-MM.")
            value = first.strftime("%d/%m/%Y")
            # Usa o mesmo resolvedor de intervalos, inclusive para fevereiro bissexto.
            last_day = calendar.monthrange(first.year, first.month)[1]
            value = f"de {value} a {last_day}/{first.month}/{first.year}"
        try:
            selected = Queries.resolve_periods(value.replace("_", " "), library, today)
        except (ValueError, OverflowError):
            return Clarification("O período selecionado contém uma data inválida.")
        if isinstance(selected, Clarification):
            return selected
        if len(selected) != 1:
            return Clarification(
                "Informe um mês (AAAA-MM), intervalo ou tipo de fatura no filtro de período."
            )

        def same_period(a: Period, b: Period) -> bool:
            return (a.start, a.end) == (b.start, b.end) if a.start and b.start else a == b

        if isinstance(periods, Clarification):
            if not selected[0].start:
                return periods
            question = re.sub(
                r"\b(" + "|".join(MONTHS) + r")(?!\w)(?!\s+(?:de\s+)?\d{4})",
                lambda m: f"{m[0]} de {selected[0].start.year}",
                normalize_text(question),
            )
            periods = Queries.resolve_periods(question, library, today)
            if isinstance(periods, Clarification):
                return periods
        if periods and (len(periods) != 1 or not same_period(periods[0], selected[0])):
            return Clarification(
                "O período selecionado e o da pergunta são diferentes. Qual devo usar?"
            )
        periods = selected
    if not periods and re.search(
        r"\bano\b|\d{1,2}/\d{1,2}|\b\d{4}\b",
        normalize_text(question),
    ):
        return Clarification("Informe o período como mês e ano ou intervalo de datas completo.")
    return periods


def has_period_data(library: Library, period: Period) -> bool:
    if period.start is None or period.end is None:
        return True
    if any(period.start <= tx.date <= period.end for tx in library.transactions):
        return True
    return any(
        st.period_start is not None
        and st.period_end is not None
        and st.period_start <= period.start
        and st.period_end >= period.end
        for st in library.statements.values()
    )


def select_chat_library(library: Library, scope: Scope) -> Library:
    """Recorta os dados e os metadados sem alterar a biblioteca da sessão."""
    # Restringe também os metadados para que cobertura e existência reflitam o recorte.
    allowed = {
        aid
        for aid, account in library.accounts.items()
        if (scope.account_ids is None or aid in scope.account_ids)
        and (scope.owner == "todas" or account.owner == scope.owner)
    }
    return replace(
        library,
        accounts={aid: a for aid, a in library.accounts.items() if aid in allowed},
        transactions=[
            tx
            for tx in library.transactions
            if ((scope.account_ids is None and scope.owner == "todas") or tx.account_id in allowed)
        ],
        statements={sid: st for sid, st in library.statements.items() if st.account_id in allowed},
    )


@dataclass(frozen=True)
class ChatSelection:
    scope: Scope
    library: Library
    periods: tuple[Period, ...]


def resolve_chat_selection(
    question: str,
    filters: FinancialFilters,
    library: Library,
    today: date,
) -> ChatSelection | Clarification:
    scope = resolve_chat_scope(question, filters, library)
    if isinstance(scope, Clarification):
        return scope
    selected = select_chat_library(library, scope)
    periods = resolve_chat_periods(question, filters, selected, today)
    if isinstance(periods, Clarification):
        return periods
    return ChatSelection(scope, selected, tuple(periods))
