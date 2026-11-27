"""Valida o documento revisado e aplica seus lançamentos de uma só vez (#96)."""

from dataclasses import replace
from threading import Lock

from app.domain.agents import IssueSeverity, ValidationIssue
from app.domain.documents import (
    DocumentConfirmRequest,
    DocumentConfirmResponse,
    DocumentKind,
    ReviewedLine,
)
from app.domain.models import (
    CONFIRMED_ORIGINS,
    Account,
    AccountKind,
    Transaction,
    TransactionNature,
    TransactionOrigin,
    TransactionType,
)
from app.services.categorization_service import CategorizationService, CategoryRuleService
from app.services.document_adapter import from_reviewed_document
from app.services.document_validation import validate_document
from app.services.library_service import Library
from app.services.statement_profiles import guess_counterparty_kind
from app.services.statement_service import account_key

_confirmation_lock = Lock()
DOCUMENT_ACCOUNT = "documentos"


class ConfirmationBlocked(Exception):
    def __init__(self, issues: list[ValidationIssue]):
        self.issues = issues
        super().__init__("; ".join(i.code for i in issues))


def _block(code: str, message: str) -> None:
    raise ConfirmationBlocked(
        [ValidationIssue(code=code, severity=IssueSeverity.BLOCKER, message=message)]
    )


def _transaction(
    req: DocumentConfirmRequest, line: ReviewedLine, account: Account, occurrence: int = 0
) -> Transaction:
    is_pix = req.kind == DocumentKind.PIX_RECEIPT
    if is_pix:
        nature = (
            TransactionNature.PIX_OUT
            if req.type == TransactionType.DEBIT
            else TransactionNature.PIX_IN
        )
    else:
        nature = (
            TransactionNature.PURCHASE
            if req.type == TransactionType.DEBIT
            else TransactionNature.OTHER
        )
    source_kind = AccountKind.CARD if req.kind == DocumentKind.CARD_INVOICE else account.kind
    manual = req.origin == "manual"
    return Transaction(
        id=f"doc:{line.date.isoformat()}:{line.amount:.2f}:{line.description.casefold()}"
        + (f":{occurrence}" if occurrence else ""),
        account_id=account.id,
        description=line.description,
        amount=float(line.amount),
        date=line.date,
        type=req.type,
        nature=nature,
        merchant=line.description,
        counterparty_kind=guess_counterparty_kind(line.description) if is_pix else None,
        category=req.category
        or CategorizationService.categorize(line.description, tx_type=req.type, nature=nature),
        source_file=(
            "lançamento digitado na tela de documento"
            if manual
            else "documento lido por foto ou PDF"
        ),
        source_kind=source_kind.value if source_kind else None,
        origin=TransactionOrigin.MANUAL if manual else TransactionOrigin.DOCUMENT,
        institution=req.bank or account.institution,
    )


def _identity(tx: Transaction) -> tuple[str, str | None, TransactionType]:
    return tx.account_id, tx.id, tx.type


def confirm_document(library: Library, req: DocumentConfirmRequest) -> DocumentConfirmResponse:
    with _confirmation_lock:
        kind = AccountKind.CARD if req.kind == DocumentKind.CARD_INVOICE else AccountKind.CHECKING
        key = req.account_id or account_key(
            DOCUMENT_ACCOUNT, "cartao" if kind == AccountKind.CARD else None
        )
        account = library.accounts.get(key)
        if req.account_id and account is None:
            _block("UNKNOWN_ACCOUNT", "Conta não encontrada.")
        if account is not None and kind == AccountKind.CARD and account.kind != AccountKind.CARD:
            _block(
                "ACCOUNT_KIND_MISMATCH", "Fatura de cartão só pode ser lançada em conta de cartão."
            )
        account = account or Account(
            id=key,
            institution=DOCUMENT_ACCOUNT,
            acct_id=DOCUMENT_ACCOUNT,
            kind=kind,
            label="Documentos lidos (foto ou PDF)",
        )
        lines = req.transactions or [
            ReviewedLine(date=req.date, description=req.description, amount=req.amount)
        ]
        # Compras idênticas no mesmo dia são legítimas: a n-ésima ocorrência ganha seu próprio id,
        # e o reenvio do mesmo documento continua reconhecido linha a linha.
        seen: dict[tuple, int] = {}
        candidates = []
        for line in lines:
            base = (line.date, line.amount, line.description.casefold())
            candidates.append(_transaction(req, line, account, seen.get(base, 0)))
            seen[base] = seen.get(base, 0) + 1
        identities = [_identity(tx) for tx in candidates]

        known = {
            _identity(tx): tx
            for tx in library.transactions
            if tx.origin in CONFIRMED_ORIGINS and not tx.is_duplicate
        }
        repeated = {known[key].uid for key in identities if key in known}
        # Só o reenvio exato sai da conciliação; os campos e o total continuam sendo validados.
        review_library = replace(
            library, transactions=[tx for tx in library.transactions if tx.uid not in repeated]
        )
        blockers = [
            issue
            for issue in validate_document(from_reviewed_document(req), review_library)
            if issue.severity == IssueSeverity.BLOCKER
        ]
        if blockers:
            raise ConfirmationBlocked(blockers)

        new = [tx for tx in candidates if _identity(tx) not in known]
        if req.category is None:
            CategoryRuleService.apply(library, new)
        results = [known.get(_identity(tx), tx) for tx in candidates]
        library.accounts[key] = account
        library.transactions.extend(new)
        return DocumentConfirmResponse(
            outcome="criado" if new else "repetido",
            uid=results[0].uid,
            uids=[tx.uid for tx in results],
            account_id=key,
            category=results[0].category,
            message="Lançamentos revisados confirmados."
            if new
            else "Este lançamento já existe; nada foi criado de novo.",
        )
