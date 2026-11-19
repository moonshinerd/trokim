"""Importação de arquivos OFX: conta, período, atualização de um mesmo período e transferências."""

from app.domain.models import (
    Account,
    AccountKind,
    AccountOwner,
    Statement,
    StatementStatus,
)
from app.services.categorization_service import CategoryRuleService
from app.services.library_service import Library
from app.services.parser_service import OfxParseResult, ParserService
from app.services.statement_service import (
    account_key,
    infer_status,
    signature,
    statement_id,
)
from app.services.transfer_service import TransferService


def bank_code(raw: str | None) -> str | None:
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    return digits.zfill(4) if digits else None


def institution_label(institution: str | None) -> str:
    return {"nubank": "Nubank", "bb": "Banco do Brasil"}.get(
        institution or "", (institution or "Banco").title()
    )


def account_label(account: Account) -> str:
    if account.label:
        return account.label
    base = institution_label(account.institution)
    if account.owner == AccountOwner.BUSINESS:
        base += " Empresas"
    kind = "cartão" if account.kind == AccountKind.CARD else "conta"
    # Cartões do BB: o final identifica qual cartão é (o usuário pode ter mais de um).
    if account.acct_id.startswith("ourocard-"):
        return f"{base} · {kind} final {account.acct_id.split('-', 1)[1]}"
    return f"{base} · {kind}"


class ImportService:
    @staticmethod
    def import_ofx(
        library: Library,
        content: bytes,
        filename: str,
        owner: AccountOwner | None = None,
    ) -> dict[str, object]:
        return ImportService.import_parsed(
            library, ParserService.parse_ofx_detailed(content, filename), filename, owner
        )

    @staticmethod
    def import_parsed(
        library: Library,
        parsed: OfxParseResult,
        filename: str,
        owner: AccountOwner | None = None,
    ) -> dict[str, object]:
        """Importa um arquivo já lido (OFX ou um PDF de perfil conhecido)."""
        meta = parsed.meta
        txs = parsed.transactions
        kind = AccountKind(meta.kind) if meta and meta.kind else None
        acct_key = account_key(parsed.institution, meta.acct_id if meta else None)

        for tx in txs:
            tx.account_id = acct_key
            tx.source_kind = kind.value if kind else None

        dates = [tx.date for tx in txs]
        period_start = (meta.period_start if meta else None) or (min(dates) if dates else None)
        period_end = (meta.period_end if meta else None) or (max(dates) if dates else None)
        generated_at = meta.generated_at if meta else None
        status, closes_on, covered_until = infer_status(
            kind, period_start, period_end, generated_at, max(dates) if dates else None
        )
        sid = statement_id(acct_key, period_start, filename)

        previous = library.statements.get(sid)
        outcome = "novo"
        delta = 0
        if previous is not None:
            old = [t for t in library.transactions if t.statement_id == sid and not t.is_duplicate]
            new_active = [t for t in txs if not t.is_duplicate]
            if signature(old) == signature(new_active):
                outcome = "repetido"
            else:
                outcome = "atualizado"
                delta = len(new_active) - len(old)
                library.transactions[:] = [t for t in library.transactions if t.statement_id != sid]

        if outcome == "repetido":
            for tx in txs:
                tx.is_duplicate = True
        else:
            ParserService.deduplicate(txs, known=library.transactions)
        for tx in txs:
            tx.statement_id = sid
        library.transactions.extend(txs)

        account = library.accounts.get(acct_key)
        if account is None:
            account = Account(
                id=acct_key,
                institution=parsed.institution,
                acct_id=(meta.acct_id if meta and meta.acct_id else "sem_conta"),
                kind=kind,
                bank_code=bank_code(meta.bank_id if meta else None),
            )
            library.accounts[acct_key] = account
        if kind and account.kind is None:
            account.kind = kind
        if owner is not None:
            account.owner = owner

        imported_active = sum(1 for tx in txs if not tx.is_duplicate)
        statement = Statement(
            id=sid,
            account_id=acct_key,
            filename=filename,
            kind=kind,
            period_start=period_start,
            period_end=period_end,
            generated_at=generated_at,
            status=status,
            covered_until=covered_until,
            closes_on=closes_on,
            ledger_balance=parsed.ledger_balance,
            imported_count=imported_active,
        )
        if previous is not None and previous.user_confirmed and previous.period_end == period_end:
            statement.user_confirmed = True
            statement.status = previous.status
            statement.closes_on = previous.closes_on
            statement.covered_until = previous.covered_until
        if outcome == "repetido" and previous is not None:
            statement = previous
        library.statements[sid] = statement

        TransferService.recompute(library)
        # Categorias que o usuário já ensinou valem também para os arquivos novos.
        CategoryRuleService.apply(library, txs)
        auto_transfers = sum(1 for tx in txs if tx.uid in library.own_marks and not tx.is_duplicate)
        return {
            "outcome": outcome,
            "delta": delta,
            "institution": parsed.institution,
            "kind": kind.value if kind else None,
            "ledger_balance": parsed.ledger_balance,
            "txs": txs,
            "account": account,
            "statement": statement,
            "reconciled": parsed.reconciled,
            "auto_transfers": auto_transfers,
            "suggestion_count": len(TransferService.suggestions(library)),
        }

    @staticmethod
    def confirm_statement(
        library: Library,
        statement: Statement,
        *,
        closed: bool | None = None,
        period_start=None,
        period_end=None,
    ) -> Statement:
        if period_start is not None:
            statement.period_start = period_start
        if period_end is not None:
            statement.period_end = period_end
        if (
            statement.period_start
            and statement.period_end
            and statement.period_start > statement.period_end
        ):
            raise ValueError("O início do período não pode ser depois do fim.")
        if closed is True:
            statement.status = StatementStatus.CLOSED
            statement.closes_on = None
            statement.covered_until = statement.period_end
            statement.user_confirmed = True
        elif closed is False:
            statement.status = (
                StatementStatus.OPEN
                if statement.kind == AccountKind.CARD
                else StatementStatus.PARTIAL
            )
            statement.closes_on = statement.period_end
            statement.user_confirmed = True
        return statement
