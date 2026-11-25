"""Consultas determinísticas sobre os dados do usuário (#94, RF30).

Camada de cálculo **sem LLM** para o agente consultar com segurança: gasto e saldo por conta e por
dono, por período (mês, intervalo, fatura aberta, fechada e próxima), parcelas em aberto, dívidas
e compromissos, top estabelecimentos e categorias, comparação entre períodos e o efeito das
transferências próprias.

Todas as funções são puras sobre a ``Library``. Os totais reaproveitam ``CalculationService``
(mesmas regras da ADR 0018: transferência própria e pagamento de fatura ficam fora) e a soma final
é feita em ``Decimal``. Cada consulta devolve ``CalculationResult`` para entrar direto na trilha
do agente.

Privacidade: o que sai é agregado, rótulo de conta (banco, tipo e dono) e estabelecimento. Nunca
documento, agência, número da conta nem nome de pessoa física.

Quando o texto é ambíguo (dois cartões do mesmo banco, mês que pode ser de mais de um ano), a
função devolve ``Clarification`` com a pergunta, e nunca um palpite silencioso. Quando o recorte
não casa com nenhuma conta, ou o período é uma fatura (sem datas), a consulta diz isso em vez de
somar tudo.
"""

import calendar
import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.domain.agents import CalculationResult
from app.domain.models import (
    Account,
    AccountKind,
    AccountOwner,
    FinancialSummary,
    Statement,
    StatementStatus,
    Transaction,
    TransactionNature,
    TransactionType,
)
from app.services.bank_registry import get_bank, list_banks
from app.services.calculation_service import CalculationService
from app.services.import_service import institution_label
from app.services.installment_service import InstallmentService, _add_months
from app.services.library_service import Library
from app.services.statement_profiles import normalize_text

SOURCE = "FinancialQueryService"
CENT = Decimal("0.01")

MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}
MONTH_NAMES = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]
STATEMENT_KINDS = ("fatura_aberta", "fatura_fechada", "proxima_fatura")


@dataclass(frozen=True)
class Clarification:
    """Pergunta de esclarecimento: no lugar de um número, quando o texto é ambíguo."""

    question: str
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class Period:
    """Período de datas (``mes`` ou ``intervalo``) ou referência a fatura (sem datas)."""

    kind: str
    label: str
    start: date | None = None
    end: date | None = None


@dataclass(frozen=True)
class Scope:
    """Recorte por conta e dono. ``account_ids=None`` significa todas as contas do dono.

    ``account_ids=()`` significa que o texto citou uma conta que não existe: nenhuma consulta
    deve somar nada nesse caso.
    """

    account_ids: tuple[str, ...] | None = None
    owner: str = "todas"
    label: str = "todas as contas"


@dataclass
class QueryResult:
    calculations: list[CalculationResult] = field(default_factory=list)
    clarification: Clarification | None = None
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- utilidades


def _d(value: float | int | str | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def _result(
    key: str, label: str, value: Decimal | int | str, unit: str | None
) -> CalculationResult:
    shown = float(value) if isinstance(value, Decimal) else value
    return CalculationResult(key=key, label=label, value=shown, unit=unit, source=SOURCE)


def _brl(key: str, label: str, value: Decimal) -> CalculationResult:
    return _result(key, label, _d(value), "BRL")


def _shift_months(day: date, months: int) -> date:
    """Soma meses mantendo o dia (ou o último dia do mês, quando ele não existe)."""
    index = day.year * 12 + (day.month - 1) + months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def _month_period(year: int, month: int) -> Period:
    start = date(year, month, 1)
    end = _add_months(start, 1) - timedelta(days=1)
    return Period("mes", f"{MONTH_NAMES[month - 1]} de {year}", start, end)


def account_name(account: Account) -> str:
    """Rótulo seguro de uma conta: banco, tipo e dono. Nunca número, agência ou documento."""
    name = institution_label(account.institution)
    kind = "cartão" if account.kind == AccountKind.CARD else "conta"
    owner = {AccountOwner.BUSINESS: "empresa", AccountOwner.PERSONAL: "pessoal"}.get(
        account.owner  # type: ignore[arg-type]
    )
    return f"{name} {kind}" + (f" ({owner})" if owner else "")


def _names(library: Library) -> dict[str, str]:
    """Rótulo por conta. Rótulos repetidos ganham um número, na ordem estável dos ids."""
    ordered = sorted(library.accounts)
    base = {aid: account_name(library.accounts[aid]) for aid in ordered}
    repeated = {name for name in base.values() if list(base.values()).count(name) > 1}
    seen: dict[str, int] = {}
    names: dict[str, str] = {}
    for aid in ordered:
        name = base[aid]
        if name in repeated:
            seen[name] = seen.get(name, 0) + 1
            name = f"{name} #{seen[name]}"
        names[aid] = name
    return names


def _bank_aliases(bank_id: str) -> set[str]:
    """Como o usuário pode chamar o banco: o id, o nome de exibição e o nome sem “Banco (do)”."""
    info = get_bank(bank_id)
    names = {normalize_text(bank_id.replace("_", " "))}
    if info:
        display = normalize_text(info.display_name)
        names |= {display, re.sub(r"^banco (?:do |de |da )?", "", display)}
    return {n for n in names if n}


def _allowed(library: Library, scope: Scope | None) -> set[str] | None:
    """Contas que o recorte permite; ``None`` = sem restrição; vazio = nenhuma."""
    scope = scope or Scope()
    allowed: set[str] | None = None if scope.account_ids is None else set(scope.account_ids)
    if scope.owner != "todas":
        owned = {
            aid
            for aid, acc in library.accounts.items()
            if acc.owner is not None and acc.owner.value == scope.owner
        }
        allowed = owned if allowed is None else allowed & owned
    return allowed


def _in_period(tx: Transaction, period: Period | None) -> bool:
    if period is None or period.start is None or period.end is None:
        return True
    return period.start <= tx.date <= period.end


def _select(
    library: Library, scope: Scope | None = None, period: Period | None = None
) -> list[Transaction]:
    allowed = _allowed(library, scope)
    return [
        tx
        for tx in library.transactions
        if (allowed is None or tx.account_id in allowed) and _in_period(tx, period)
    ]


def _summary(
    txs: Sequence[Transaction], view: str = "competencia", merchant_limit: int = 5
) -> FinancialSummary:
    return CalculationService.calculate_summary(txs, view=view, merchant_limit=merchant_limit)


def _unclassified_note(library: Library, scope: Scope | None) -> list[str]:
    """Avisa quando o filtro por dono deixou de fora contas ainda sem dono."""
    if scope is None or scope.owner == "todas":
        return []
    allowed = _allowed(library, Scope(scope.account_ids))
    pending = [
        aid
        for aid, acc in library.accounts.items()
        if acc.owner is None and (allowed is None or aid in allowed)
    ]
    if not pending:
        return []
    return [
        f"{len(pending)} conta(s) ainda sem dono (pessoal ou empresa) ficaram de fora deste total."
    ]


def _period_text(period: Period | None) -> str:
    return f" em {period.label}" if period else ""


def _guard(library: Library, scope: Scope | None, *periods: Period | None) -> QueryResult | None:
    """Recusa o que daria um número sem sentido: conta inexistente ou período sem datas."""
    for period in periods:
        if period is not None and period.start is None:
            return QueryResult(
                notes=[
                    f"“{period.label}” é uma fatura, não um intervalo de datas. "
                    "Use as consultas de fatura (statement_total ou next_statement)."
                ]
            )
    allowed = _allowed(library, scope)
    if allowed is not None and not allowed:
        return QueryResult(notes=["Nenhuma conta importada combina com esse recorte."])
    return None


# ------------------------------------------------------------------------ consultas


class FinancialQueryService:
    """Consultas puras sobre a biblioteca local; cada uma devolve ``QueryResult``."""

    # ---- por conta e por dono -------------------------------------------------------

    @staticmethod
    def by_account(
        library: Library, period: Period | None = None, view: str = "competencia"
    ) -> QueryResult:
        """Gasto, receita e saldo de cada conta (rótulo seguro) no período.

        A chave ``account_<h>_*`` usa um hash curto do id da conta: estável quando outra conta
        entra, e sem expor o id (que carrega o número da conta).
        """
        if blocked := _guard(library, None, period):
            return blocked
        names = _names(library)
        out = QueryResult()
        for account_id in sorted(names):
            txs = _select(library, Scope((account_id,)), period)
            if not txs:
                continue
            index = hashlib.sha1(account_id.encode()).hexdigest()[:8]
            summary = _summary(txs, view)
            name = names[account_id]
            suffix = _period_text(period)
            out.calculations += [
                _brl(
                    f"account_{index}_expenses",
                    f"Gasto em {name}{suffix}",
                    _d(summary.total_expenses),
                ),
                _brl(
                    f"account_{index}_income",
                    f"Receita em {name}{suffix}",
                    _d(summary.total_income),
                ),
                _brl(
                    f"account_{index}_balance",
                    f"Saldo de {name}{suffix}",
                    _d(summary.net_balance),
                ),
            ]
        if not out.calculations:
            out.notes.append("Nenhum lançamento nas contas para o período.")
        return out

    @staticmethod
    def by_owner(
        library: Library, owner: str, period: Period | None = None, view: str = "competencia"
    ) -> QueryResult:
        """Gasto, receita e saldo de um dono (``pessoal`` ou ``empresa``)."""
        if owner not in {"pessoal", "empresa"}:
            return QueryResult(
                clarification=Clarification(
                    "As contas são pessoais ou da empresa?", ("pessoal", "empresa")
                )
            )
        if blocked := _guard(library, None, period):
            return blocked
        summary = _summary(_select(library, Scope(owner=owner), period), view)
        suffix = f" ({owner}){_period_text(period)}"
        return QueryResult(
            [
                _brl("owner_expenses", f"Gasto{suffix}", _d(summary.total_expenses)),
                _brl("owner_income", f"Receita{suffix}", _d(summary.total_income)),
                _brl("owner_balance", f"Saldo{suffix}", _d(summary.net_balance)),
            ],
            notes=_unclassified_note(library, Scope(owner=owner)),
        )

    @staticmethod
    def totals(
        library: Library,
        scope: Scope | None = None,
        period: Period | None = None,
        view: str = "competencia",
    ) -> QueryResult:
        """Gasto, receita e saldo de um recorte (conta, dono e período) já resolvido."""
        scope = scope or Scope()
        if blocked := _guard(library, scope, period):
            return blocked
        summary = _summary(_select(library, scope, period), view)
        suffix = f" ({scope.label}){_period_text(period)}"
        return QueryResult(
            [
                _brl("total_expenses", f"Gasto{suffix}", _d(summary.total_expenses)),
                _brl("total_income", f"Receita{suffix}", _d(summary.total_income)),
                _brl("net_balance", f"Saldo{suffix}", _d(summary.net_balance)),
            ],
            notes=_unclassified_note(library, scope),
        )

    # ---- faturas --------------------------------------------------------------------

    @staticmethod
    def _card_statements(
        library: Library, status: StatementStatus, scope: Scope | None
    ) -> list[Statement]:
        """Uma fatura por cartão: a aberta, ou a fechada mais recente."""
        allowed = _allowed(library, scope)
        latest: dict[str, Statement] = {}
        for st in library.statements.values():
            account = library.accounts.get(st.account_id)
            is_card = st.kind == AccountKind.CARD or (account and account.kind == AccountKind.CARD)
            if not is_card or st.status != status:
                continue
            if allowed is not None and st.account_id not in allowed:
                continue
            current = latest.get(st.account_id)
            if current is None or (st.period_end or date.min) > (current.period_end or date.min):
                latest[st.account_id] = st
        return list(latest.values())

    @staticmethod
    def _which_card(library: Library, found: list[Statement], kind: str) -> QueryResult:
        names = _names(library)
        return QueryResult(
            clarification=Clarification(
                f"Há mais de um cartão com fatura {kind}. De qual você quer saber?",
                tuple(sorted(names[st.account_id] for st in found)),
            )
        )

    @staticmethod
    def statement_total(library: Library, kind: str, scope: Scope | None = None) -> QueryResult:
        """Total da fatura ``aberta`` ou ``fechada``. Mais de um cartão: pede esclarecimento."""
        if kind not in ("aberta", "fechada"):
            return QueryResult(
                notes=[f"Fatura “{kind}” não existe aqui; use “aberta” ou “fechada”."]
            )
        if blocked := _guard(library, scope):
            return blocked
        status = StatementStatus.OPEN if kind == "aberta" else StatementStatus.CLOSED
        found = FinancialQueryService._card_statements(library, status, scope)
        if not found:
            return QueryResult(notes=[f"Não há fatura {kind} importada."])
        if len(found) > 1:
            return FinancialQueryService._which_card(library, found, kind)
        statement = found[0]
        name = _names(library)[statement.account_id]
        txs = [tx for tx in library.transactions if tx.statement_id == statement.id]
        total = _d(_summary(txs).total_expenses)
        out = QueryResult([_brl(f"statement_{kind}", f"Fatura {kind} de {name}", total)])
        if statement.period_start and statement.period_end:
            out.notes.append(
                f"Ciclo de {statement.period_start:%d/%m/%Y} a {statement.period_end:%d/%m/%Y}."
            )
        if kind == "aberta" and statement.closes_on:
            out.notes.append(f"A fatura fecha em {statement.closes_on:%d/%m/%Y}.")
        if statement.due_date:
            out.notes.append(f"Vencimento em {statement.due_date:%d/%m/%Y}.")
        return out

    @staticmethod
    def next_statement(library: Library, today: date, scope: Scope | None = None) -> QueryResult:
        """Próxima fatura: as parcelas já contratadas cuja data cai no próximo ciclo.

        O próximo ciclo começa no dia seguinte ao fechamento da fatura aberta e dura um mês. Sem
        fatura aberta, vale o mês calendário seguinte a ``today``. O valor é exato para o que já
        foi contratado, mas a data de cada parcela é estimada pelo mês (última parcela vista mais
        k meses). Compras novas ainda não existem e não entram.
        """
        if blocked := _guard(library, scope):
            return blocked
        opened = FinancialQueryService._card_statements(library, StatementStatus.OPEN, scope)
        if len(opened) > 1:
            return FinancialQueryService._which_card(library, opened, "aberta")
        closing = (opened[0].closes_on or opened[0].period_end) if opened else None
        if closing is not None:
            start = closing + timedelta(days=1)
            end = _shift_months(closing, 1)
            if closing.day == calendar.monthrange(closing.year, closing.month)[1]:
                # Fechamento no último dia do mês: o próximo também fecha no último dia.
                end = _shift_months(closing, 1).replace(
                    day=calendar.monthrange(end.year, end.month)[1]
                )
        else:
            first = _add_months(date(today.year, today.month, 1), 1)
            start, end = first, _add_months(first, 1) - timedelta(days=1)
        plan = InstallmentService.build(_select(library, scope))
        total = Decimal(0)
        for item in plan["plans"]:  # type: ignore[attr-defined,union-attr]
            if item["finished"]:
                continue
            last = date.fromisoformat(str(item["last_seen"]))
            for k in range(1, int(item["remaining"]) + 1):
                if start <= _shift_months(last, k) <= end:
                    total += _d(item["amount"])
        return QueryResult(
            [
                _brl(
                    "next_statement_installments",
                    f"Parcelas já contratadas no próximo ciclo ({start:%d/%m/%Y} a {end:%d/%m/%Y})",
                    total,
                )
            ],
            notes=[
                "Só entram as parcelas já contratadas; compras novas não entram.",
                "A data de cada parcela é estimada pelo mês da última parcela vista.",
            ],
        )

    # ---- parcelas e dívidas ---------------------------------------------------------

    @staticmethod
    def open_installments(library: Library, scope: Scope | None = None) -> QueryResult:
        """Quanto falta pagar, valor mensal e quando terminam os parcelamentos em aberto."""
        if blocked := _guard(library, scope):
            return blocked
        plan = InstallmentService.build(_select(library, scope))
        active = [p for p in plan["plans"] if not p["finished"]]  # type: ignore[attr-defined,union-attr]
        if not active:
            return QueryResult(notes=["Não há parcelas em aberto."])
        remaining = sum((_d(p["remaining_amount"]) for p in active), Decimal(0))
        monthly = sum((_d(p["amount"]) for p in active), Decimal(0))
        ends = max(str(p["ends_on_month"]) for p in active)
        return QueryResult(
            [
                _brl("installments_remaining", "Falta pagar em parcelas", remaining),
                _brl("installments_monthly", "Valor mensal das parcelas em aberto", monthly),
                _result("installments_ends_on", "Última parcela em aberto termina em", ends, None),
                _result("installments_active", "Parcelamentos em aberto", len(active), "un"),
            ]
        )

    @staticmethod
    def commitments(
        library: Library, today: date, scope: Scope | None = None, window_days: int = 30
    ) -> QueryResult:
        """Dívidas e compromissos, cada número com a base que o sustenta.

        - ``installments_future``: parcelas que ainda faltam (exato).
        - ``closed_statement_due``: total da última fatura fechada de cada cartão menos os
          pagamentos de fatura lançados no cartão depois do fechamento (exato).
        - ``due_next_N_days``: da fatura fechada a pagar, só o que tem **vencimento informado**
          dentro da janela (``Statement.due_date``, lido dos PDFs do Itaú e do PicPay).
        - ``overdue_statement_due``: a fatura fechada a pagar cujo vencimento informado já passou.
        - ``closed_due_without_date``: a parte da fatura fechada a pagar cujo arquivo não traz o
          vencimento. Não é chutada para dentro nem para fora da janela.
        - ``installments_in_window``: parcelas cuja data (a das parcelas já vistas, mês a mês)
          cai na janela.
        """
        if blocked := _guard(library, scope):
            return blocked
        pool = _select(library, scope)
        plan = InstallmentService.build(pool)
        active = [p for p in plan["plans"] if not p["finished"]]  # type: ignore[attr-defined,union-attr]
        future = sum((_d(p["remaining_amount"]) for p in active), Decimal(0))
        window_end = today + timedelta(days=window_days)

        due_total = Decimal(0)
        due_in_window = Decimal(0)
        due_unknown = Decimal(0)
        overdue = Decimal(0)
        for st in FinancialQueryService._card_statements(library, StatementStatus.CLOSED, scope):
            st_txs = [tx for tx in pool if tx.statement_id == st.id]
            total = _d(_summary(st_txs).total_expenses)
            # Nos PDFs do Itaú e do PicPay o fim do período é o próprio vencimento; o corte dos
            # pagamentos passa a ser a última compra da fatura.
            cutoff = st.period_end
            if st.due_date is not None and st.period_end == st.due_date and st_txs:
                cutoff = max(tx.date for tx in st_txs)
            paid = sum(
                (
                    _d(tx.amount)
                    for tx in pool
                    if tx.account_id == st.account_id
                    and tx.type == TransactionType.CREDIT
                    and tx.nature == TransactionNature.CARD_PAYMENT
                    and not tx.is_duplicate
                    and cutoff is not None
                    and tx.date > cutoff
                ),
                Decimal(0),
            )
            owed = max(total - paid, Decimal(0))
            # O PDF do cartão não traz o pagamento: ele sai da conta corrente. Um débito de
            # pagamento de fatura de exatamente o valor devido, depois do corte, quita a fatura.
            if owed > 0 and cutoff is not None:
                owner = (library.accounts.get(st.account_id) or Account(id="", acct_id="")).owner
                for tx in pool:
                    acc = library.accounts.get(tx.account_id)
                    if (
                        tx.type == TransactionType.DEBIT
                        and tx.nature == TransactionNature.CARD_PAYMENT
                        and not tx.is_duplicate
                        and tx.date > cutoff
                        and acc is not None
                        and acc.kind != AccountKind.CARD
                        and (owner is None or acc.owner in (None, owner))
                        and _d(tx.amount) == owed
                    ):
                        owed = Decimal(0)
                        break
            due_total += owed
            if st.due_date is None:
                due_unknown += owed
            elif st.due_date < today:
                overdue += owed
            elif st.due_date <= window_end:
                due_in_window += owed

        in_window = Decimal(0)
        for item in active:
            last = date.fromisoformat(str(item["last_seen"]))
            for k in range(1, int(item["remaining"]) + 1):
                if today <= _shift_months(last, k) <= window_end:
                    in_window += _d(item["amount"])

        out = QueryResult(
            [
                _brl("installments_future", "Parcelas futuras a pagar", future),
                _brl("closed_statement_due", "Fatura fechada a pagar", due_total),
                _brl(
                    f"due_next_{window_days}_days",
                    f"Fatura fechada com vencimento nos próximos {window_days} dias",
                    due_in_window,
                ),
                _brl("overdue_statement_due", "Fatura fechada vencida e não paga", overdue),
                _brl(
                    "closed_due_without_date",
                    "Fatura fechada a pagar sem vencimento informado no arquivo",
                    due_unknown,
                ),
                _brl(
                    "installments_in_window",
                    f"Parcelas previstas nos próximos {window_days} dias",
                    in_window,
                ),
            ]
        )
        out.notes.append(
            "A data das parcelas previstas é estimada pelo mês da última parcela vista."
        )
        if due_unknown > 0:
            out.notes.append(
                "O arquivo de alguma fatura fechada não traz o vencimento (OFX não traz); "
                "esse valor não entra na janela e aparece separado."
            )
        return out

    # ---- ranking, comparação e transferências ---------------------------------------

    @staticmethod
    def top_merchants(
        library: Library,
        period: Period | None = None,
        scope: Scope | None = None,
        limit: int = 5,
    ) -> QueryResult:
        """Estabelecimentos com mais gasto no período (Pix para pessoas vira um grupo só)."""
        if blocked := _guard(library, scope, period):
            return blocked
        summary = _summary(_select(library, scope, period), merchant_limit=limit)
        top = summary.top_merchants[:limit]
        if not top:
            return QueryResult(notes=["Sem gastos por estabelecimento no período."])
        return QueryResult(
            [
                _brl(
                    f"top_merchant_{i}",
                    f"{row['merchant']}{_period_text(period)}",
                    _d(row["total"]),  # type: ignore[arg-type]
                )
                for i, row in enumerate(top, start=1)
            ]
        )

    @staticmethod
    def top_categories(
        library: Library,
        period: Period | None = None,
        scope: Scope | None = None,
        limit: int = 5,
    ) -> QueryResult:
        """Categorias com mais gasto no período."""
        if blocked := _guard(library, scope, period):
            return blocked
        summary = _summary(_select(library, scope, period))
        ranked = sorted(summary.expenses_by_category.items(), key=lambda kv: (-kv[1], kv[0]))
        if not ranked:
            return QueryResult(notes=["Sem gastos por categoria no período."])
        return QueryResult(
            [
                _brl(f"top_category_{i}", f"Categoria {name}{_period_text(period)}", _d(value))
                for i, (name, value) in enumerate(ranked[:limit], start=1)
            ]
        )

    @staticmethod
    def compare_periods(
        library: Library,
        first: Period,
        second: Period,
        scope: Scope | None = None,
        view: str = "competencia",
    ) -> QueryResult:
        """Gasto em dois períodos, diferença e variação percentual (só com base positiva)."""
        if blocked := _guard(library, scope, first, second):
            return blocked
        a = _d(_summary(_select(library, scope, first), view).total_expenses)
        b = _d(_summary(_select(library, scope, second), view).total_expenses)
        delta = b - a
        out = QueryResult(
            [
                _brl("compare_first", f"Gasto em {first.label}", a),
                _brl("compare_second", f"Gasto em {second.label}", b),
                _brl("compare_delta", f"Diferença de {first.label} para {second.label}", delta),
            ]
        )
        if a > 0:
            pct = (delta / a * 100).quantize(CENT, rounding=ROUND_HALF_UP)
            out.calculations.append(
                _result("compare_pct", f"Variação de {first.label} para {second.label}", pct, "%")
            )
        else:
            out.notes.append(f"Sem gasto em {first.label}: a variação percentual não se aplica.")
        return out

    @staticmethod
    def own_transfers_effect(
        library: Library, period: Period | None = None, scope: Scope | None = None
    ) -> QueryResult:
        """Quanto saiu das contas só por transferência própria e pagamento de fatura.

        Esses valores ficam **fora** dos totais (ADR 0018): esta consulta mostra o que foi
        deixado de fora, para explicar a diferença entre o saldo da conta e o gasto real.
        """
        if blocked := _guard(library, scope, period):
            return blocked
        txs = [
            tx
            for tx in _select(library, scope, period)
            if not tx.is_duplicate
            and tx.type == TransactionType.DEBIT
            and tx.nature in (TransactionNature.INTERNAL_TRANSFER, TransactionNature.CARD_PAYMENT)
        ]
        own = sum(
            (_d(t.amount) for t in txs if t.nature == TransactionNature.INTERNAL_TRANSFER),
            Decimal(0),
        )
        card = sum(
            (_d(t.amount) for t in txs if t.nature == TransactionNature.CARD_PAYMENT),
            Decimal(0),
        )
        suffix = _period_text(period)
        return QueryResult(
            [
                _brl(
                    "own_transfers_out", f"Transferências próprias (fora dos totais){suffix}", own
                ),
                _brl("card_payments_out", f"Pagamentos de fatura (fora dos totais){suffix}", card),
            ]
        )

    # ---- resolução de período e de conta a partir do texto --------------------------

    @staticmethod
    def resolve_periods(text: str, library: Library, today: date) -> list[Period] | Clarification:
        """Todos os períodos citados no texto, na ordem; ``[]`` se não há nenhum."""
        norm = normalize_text(text)
        found: list[tuple[int, Period]] = []

        def add(pos: int, period: Period) -> None:
            if all(period != existing for _, existing in found):
                found.append((pos, period))

        for kind, pattern, label in (
            ("fatura_aberta", r"fatura (?:aberta|atual)", "fatura aberta"),
            ("fatura_fechada", r"fatura fechada", "fatura fechada"),
            ("proxima_fatura", r"proxima fatura", "próxima fatura"),
        ):
            if m := re.search(pattern, norm):
                add(m.start(), Period(kind, label))

        for m in re.finditer(r"\b(?:mes passado|ultimo mes|mes anterior)\b", norm):
            prev = _add_months(date(today.year, today.month, 1), -1)
            add(m.start(), _month_period(prev.year, prev.month))
        for m in re.finditer(r"\b(?:este mes|neste mes|mes atual|esse mes|nesse mes)\b", norm):
            add(m.start(), _month_period(today.year, today.month))
        for m in re.finditer(r"\bultimos (\d{1,3}) dias\b", norm):
            days = int(m[1])
            if days < 1:
                return Clarification("Quantos dias? Informe um número maior que zero.")
            add(
                m.start(),
                Period(
                    "intervalo", f"últimos {days} dias", today - timedelta(days=days - 1), today
                ),
            )

        for m in re.finditer(
            r"\b(?:de|entre|do dia)\s+(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\s+(?:a|ate|e)\s+"
            r"(\d{1,2})/(\d{1,2})(?:/(\d{4}))?",
            norm,
        ):
            try:
                start = date(int(m[3] or today.year), int(m[2]), int(m[1]))
                end = date(int(m[6] or today.year), int(m[5]), int(m[4]))
            except ValueError:
                return Clarification("Não entendi as datas do intervalo. Pode informar de novo?")
            if end < start:
                return Clarification(
                    "A data final vem antes da inicial. Qual é o intervalo correto?"
                )
            add(m.start(), Period("intervalo", f"{start:%d/%m/%Y} a {end:%d/%m/%Y}", start, end))

        for m in re.finditer(r"\b(" + "|".join(MONTHS) + r")(?:\s+de)?(?:\s+(\d{4}))?\b", norm):
            month = MONTHS[m[1]]
            if m[2]:
                add(m.start(), _month_period(int(m[2]), month))
                continue
            # Sem ano: o candidato natural é o último `month` que já passou; os anos em que há
            # lançamentos naquele mês também entram. Mais de um candidato: pergunta, não palpite.
            natural = today.year if month <= today.month else today.year - 1
            data_years = {tx.date.year for tx in library.transactions if tx.date.month == month}
            years = sorted({natural} | data_years)
            if len(years) > 1:
                return Clarification(
                    f"{MONTH_NAMES[month - 1].capitalize()} de qual ano?",
                    tuple(str(y) for y in years),
                )
            add(m.start(), _month_period(years[0], month))

        found.sort(key=lambda item: item[0])
        return [period for _, period in found]

    @staticmethod
    def resolve_period(text: str, library: Library, today: date) -> Period | Clarification | None:
        """O período do texto, ``None`` se não há, ou pedido de esclarecimento se há vários."""
        periods = FinancialQueryService.resolve_periods(text, library, today)
        if isinstance(periods, Clarification):
            return periods
        if not periods:
            return None
        if len(periods) > 1:
            return Clarification(
                "Mais de um período no texto. Qual deles você quer?",
                tuple(p.label for p in periods),
            )
        return periods[0]

    @staticmethod
    def resolve_scope(text: str, library: Library) -> Scope | Clarification:
        """Conta e dono citados no texto (“fatura do Nubank”, “empresa”). Ambíguo: pergunta."""
        norm = normalize_text(text)
        owner = "todas"
        if re.search(r"\b(?:empresa|empresas|pj|cnpj)\b", norm):
            owner = "empresa"
        elif re.search(r"\b(?:pessoal|pessoais|pf|pessoa fisica)\b", norm):
            owner = "pessoal"
        wants_card = bool(re.search(r"\b(?:cartao|fatura|faturas)\b", norm))
        explicit_account = bool(re.search(r"\bconta (?:corrente|do|da)\b|\bextrato\b", norm))
        bare_account = bool(re.search(r"\bconta\b", norm))

        wants_account = False

        def fits(acc: Account) -> bool:
            return (
                (owner == "todas" or (acc.owner is not None and acc.owner.value == owner))
                and (not wants_card or acc.kind == AccountKind.CARD)
                and (not wants_account or acc.kind in (AccountKind.CHECKING, None))
            )

        def mentions(aliases: set[str]) -> bool:
            # Palavra inteira: “inter” não pode casar com “internacional”.
            return any(re.search(rf"\b{re.escape(alias)}\b", norm) for alias in aliases)

        institutions = {aid: acc.institution for aid, acc in library.accounts.items()}
        mentioned = {
            inst for inst in set(institutions.values()) if inst and mentions(_bank_aliases(inst))
        }
        # “conta” sozinha só restringe quando há banco no texto (“conta nubank”); “conta de luz”,
        # sem banco, não vira filtro.
        wants_account = not wants_card and (explicit_account or (bare_account and bool(mentioned)))
        if not mentioned:
            # Banco que o Trokim conhece, citado no texto, mas sem conta importada: nada a somar.
            unknown = [b.bank_id for b in list_banks() if mentions(_bank_aliases(b.bank_id))]
            if unknown:
                return Scope((), owner, ", ".join(sorted(institution_label(u) for u in unknown)))
            if owner == "todas" and not (wants_card or wants_account):
                return Scope()
            if not (wants_card or wants_account):
                return Scope(None, owner, owner)
            ids = tuple(aid for aid, acc in library.accounts.items() if fits(acc))
            label = owner if owner != "todas" else ("cartões" if wants_card else "contas")
            return Scope(ids, owner, label)

        names = _names(library)
        matches = [
            aid
            for aid, acc in library.accounts.items()
            if institutions[aid] in mentioned and fits(acc)
        ]
        if not matches:
            return Scope((), owner, ", ".join(sorted(institution_label(m) for m in mentioned)))
        per_bank: dict[str, int] = {}
        for aid in matches:
            per_bank[institutions[aid]] = per_bank.get(institutions[aid], 0) + 1
        if any(count > 1 for count in per_bank.values()):
            return Clarification(
                "Encontrei mais de uma conta que combina. Qual delas?",
                tuple(sorted(names[aid] for aid in matches)),
            )
        return Scope(tuple(matches), owner, ", ".join(names[aid] for aid in matches))
