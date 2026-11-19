"""Situação e cobertura dos arquivos importados (fatura aberta ou fechada, lacunas)."""

import hashlib
from collections.abc import Iterable
from datetime import date, timedelta

from app.domain.models import (
    AccountKind,
    Statement,
    StatementStatus,
    Transaction,
)


def account_key(institution: str | None, acct_id: str | None) -> str:
    return f"{institution or 'generico'}:{acct_id or 'sem_conta'}"


def statement_id(account_id: str, period_start: date | None, filename: str) -> str:
    raw = f"{account_id}|{period_start.isoformat() if period_start else filename}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def infer_status(
    kind: AccountKind | None,
    period_start: date | None,
    period_end: date | None,
    generated_at: date | None,
    last_posted: date | None = None,
) -> tuple[StatementStatus, date | None, date | None]:
    """Devolve (situação, fecha em, coberto até).

    Regra (confirmada com faturas reais do Nubank): o OFX traz o ciclo em ``DTSTART``/``DTEND``
    e o momento da geração em ``DTSERVER``. Se o fim do ciclo é igual ou posterior à geração, o
    período ainda não terminou (fatura aberta, ou extrato parcial). Igual conta como incompleto:
    o dia da geração ainda não acabou. Sem esses campos, a situação é desconhecida.
    """
    if period_end is None or generated_at is None:
        return StatementStatus.UNKNOWN, None, last_posted
    if period_end >= generated_at:
        status = StatementStatus.OPEN if kind == AccountKind.CARD else StatementStatus.PARTIAL
        covered = min(period_end, generated_at)
        if last_posted is not None:
            covered = min(covered, max(last_posted, period_start or last_posted))
        return status, period_end, covered
    return StatementStatus.CLOSED, None, period_end


def reconcile_status(statement: Statement) -> Statement:
    """Recalcula a situação depois que o usuário ajusta o período (sem mexer na confirmação)."""
    if statement.user_confirmed:
        return statement
    status, closes_on, covered = infer_status(
        statement.kind,
        statement.period_start,
        statement.period_end,
        statement.generated_at,
        statement.covered_until,
    )
    statement.status, statement.closes_on, statement.covered_until = status, closes_on, covered
    return statement


def signature(transactions: Iterable[Transaction]) -> frozenset[tuple]:
    """Conteúdo de um arquivo, para saber se um reenvio é igual ao anterior."""
    return frozenset(
        (tx.id or "", tx.date, round(tx.amount, 2), tx.type.value, tx.description)
        for tx in transactions
    )


def coverage(statements: Iterable[Statement]) -> dict[str, dict[str, object]]:
    """Por conta: arquivos em ordem, lacunas entre eles e se o último ainda está aberto."""
    by_account: dict[str, list[Statement]] = {}
    for item in statements:
        by_account.setdefault(item.account_id, []).append(item)
    result: dict[str, dict[str, object]] = {}
    for account_id, items in by_account.items():
        ordered = sorted(
            items, key=lambda s: (s.period_start or date.max, s.period_end or date.max)
        )
        gaps: list[dict[str, str]] = []
        previous_end: date | None = None
        for item in ordered:
            if previous_end and item.period_start:
                start_expected = previous_end + timedelta(days=1)
                if item.period_start > start_expected:
                    gaps.append(
                        {
                            "from": start_expected.isoformat(),
                            "to": (item.period_start - timedelta(days=1)).isoformat(),
                        }
                    )
            if item.period_end and (previous_end is None or item.period_end > previous_end):
                previous_end = item.period_end
        result[account_id] = {
            "statement_ids": [s.id for s in ordered],
            "gaps": gaps,
            "has_open": any(
                s.status in (StatementStatus.OPEN, StatementStatus.PARTIAL) for s in ordered
            ),
            "covered_from": min((s.period_start for s in ordered if s.period_start), default=None),
            "covered_until": max(
                (
                    s.covered_until or s.period_end
                    for s in ordered
                    if s.covered_until or s.period_end
                ),
                default=None,
            ),
        }
    return result
