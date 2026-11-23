"""Confirmação de um documento revisado: vira um lançamento na biblioteca (#96).

Só chega aqui o que o usuário revisou e aprovou. A validação (#89) roda de novo sobre os campos
confirmados: qualquer bloqueio recusa a criação. Reenviar o mesmo documento não duplica: a
deduplicação existente (data, descrição e valor) responde "repetido" e nada é criado.
"""

from decimal import Decimal

from app.domain.agents import IssueSeverity, ValidationIssue
from app.domain.document import DocumentType
from app.domain.document import ExtractedDocument as ValidationDocument
from app.domain.documents import (
    DOCUMENT_SOURCE,
    DocumentConfirmRequest,
    DocumentConfirmResponse,
    DocumentKind,
)
from app.domain.models import (
    Account,
    AccountKind,
    Transaction,
    TransactionNature,
    TransactionType,
)
from app.services.categorization_service import CategorizationService, CategoryRuleService
from app.services.document_validation import validate_document
from app.services.library_service import Library
from app.services.parser_service import ParserService
from app.services.statement_service import account_key

DOCUMENT_ACCOUNT = "documentos"

_TYPES = {
    DocumentKind.PIX_RECEIPT: DocumentType.PIX,
    DocumentKind.BOLETO: DocumentType.BOLETO,
    DocumentKind.CARD_INVOICE: DocumentType.FATURA,
}


class ConfirmationBlocked(Exception):
    def __init__(self, issues: list[ValidationIssue]):
        self.issues = issues
        super().__init__("; ".join(i.code for i in issues))


def _nature(req: DocumentConfirmRequest) -> TransactionNature:
    if req.kind == DocumentKind.PIX_RECEIPT:
        return (
            TransactionNature.PIX_OUT
            if req.type == TransactionType.DEBIT
            else TransactionNature.PIX_IN
        )
    return (
        TransactionNature.PURCHASE if req.type == TransactionType.DEBIT else TransactionNature.OTHER
    )


def confirm_document(library: Library, req: DocumentConfirmRequest) -> DocumentConfirmResponse:
    amount = req.amount.quantize(Decimal("0.01"))
    nature = _nature(req)
    key = account_key(DOCUMENT_ACCOUNT, None)
    tx = Transaction(
        id=f"doc:{req.date.isoformat()}:{amount}:{req.description.casefold()}",
        account_id=key,
        description=req.description,
        amount=float(amount),
        date=req.date,
        type=req.type,
        nature=nature,
        merchant=req.description if nature == TransactionNature.PURCHASE else None,
        category=req.category
        or CategorizationService.categorize(req.description, tx_type=req.type, nature=nature),
        source_file="documento lido por foto ou PDF",
        source_kind=DOCUMENT_SOURCE,
        institution=req.bank or DOCUMENT_ACCOUNT,
    )

    # Mesmo documento reenviado: a deduplicação existente decide, antes de validar de novo.
    probe = tx.model_copy()
    ParserService.deduplicate([probe], known=library.transactions)
    if probe.is_duplicate:
        existing = next(
            t
            for t in library.transactions
            if not t.is_duplicate
            and (t.date, t.description.casefold(), round(t.amount, 2))
            == (tx.date, tx.description.casefold(), round(tx.amount, 2))
        )
        return DocumentConfirmResponse(
            outcome="repetido",
            uid=existing.uid,
            account_id=existing.account_id,
            category=existing.category,
            message="Este lançamento já existe; nada foi criado de novo.",
        )

    blockers = [
        i
        for i in validate_document(
            ValidationDocument(
                document_type=_TYPES.get(req.kind, DocumentType.OUTRO),
                amount=amount,
                raw_amount=str(amount),
                date=req.date,
                recipient=req.description,
                merchant=req.description,
                institution=req.bank,
            ),
            library,
        )
        if i.severity == IssueSeverity.BLOCKER
    ]
    if blockers:
        raise ConfirmationBlocked(blockers)

    if key not in library.accounts:
        library.accounts[key] = Account(
            id=key,
            institution=DOCUMENT_ACCOUNT,
            acct_id=DOCUMENT_ACCOUNT,
            kind=AccountKind.CHECKING,
            label="Documentos lidos (foto ou PDF)",
        )
    library.transactions.append(tx)
    if req.category is None:
        CategoryRuleService.apply(library, [tx])  # regra que o usuário já ensinou
    return DocumentConfirmResponse(
        outcome="criado",
        uid=tx.uid,
        account_id=key,
        category=tx.category,
        message="Lançamento criado a partir do documento que você confirmou.",
    )
