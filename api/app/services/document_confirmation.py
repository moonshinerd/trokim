"""Confirmação de um documento revisado: vira um lançamento na biblioteca (#96).

Só chega aqui o que o usuário revisou e aprovou. A validação (#89) roda de novo sobre os campos
confirmados: qualquer bloqueio recusa a criação. Reenviar o mesmo documento não duplica: a
deduplicação existente (data, descrição e valor) responde "repetido" e nada é criado.
"""

from dataclasses import replace
from decimal import Decimal
from threading import Lock

from app.domain.agents import IssueSeverity, ValidationIssue
from app.domain.document import DocumentType, ExtractedLine
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
from app.services.statement_service import account_key

_confirmation_lock = Lock()
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
    with _confirmation_lock:
        if not req.transactions:
            result = _confirm(library, req)
            result.uids = [result.uid]
            return result
        document = ValidationDocument(
            document_type=_TYPES.get(req.kind, DocumentType.OUTRO),
            date=req.date,
            due_date=req.due_date,
            amount=req.amount,
            merchant=req.description,
            institution=req.bank,
            lines=[ExtractedLine(**line.model_dump()) for line in req.transactions],
        )
        blockers = [
            i for i in validate_document(document, None) if i.severity == IssueSeverity.BLOCKER
        ]
        if blockers:
            raise ConfirmationBlocked(blockers)
        staged = replace(
            library, accounts=dict(library.accounts), transactions=list(library.transactions)
        )
        results = [
            _confirm(staged, req.model_copy(update={**line.model_dump(), "transactions": []}))
            for line in req.transactions
        ]
        if len({item.uid for item in results}) != len(results):
            raise ConfirmationBlocked(
                [
                    ValidationIssue(
                        code="POSSIBLE_DUPLICATE",
                        severity=IssueSeverity.BLOCKER,
                        message="Há linhas idênticas na fatura. Revise os itens.",
                    )
                ]
            )
        library.accounts.update(staged.accounts)
        library.transactions.extend(staged.transactions[len(library.transactions) :])
        result = results[0].model_copy()
        result.uids = [item.uid for item in results]
        if any(item.outcome == "criado" for item in results):
            result.outcome = "criado"
            result.message = "Lançamentos revisados confirmados."
        return result


def _confirm(library: Library, req: DocumentConfirmRequest) -> DocumentConfirmResponse:
    amount = req.amount.quantize(Decimal("0.01"))
    nature = _nature(req)
    key = req.account_id or account_key(DOCUMENT_ACCOUNT, None)
    if req.account_id and key not in library.accounts:
        raise ConfirmationBlocked(
            [
                ValidationIssue(
                    code="UNKNOWN_ACCOUNT",
                    severity=IssueSeverity.BLOCKER,
                    message="Conta não encontrada.",
                )
            ]
        )
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
    existing = next(
        (
            item
            for item in library.transactions
            if item.source_kind == DOCUMENT_SOURCE
            and item.account_id == key
            and item.id == tx.id
            and item.type == tx.type
            and not item.is_duplicate
        ),
        None,
    )
    if existing is not None:
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
                due_date=req.due_date,
                account_id=key,
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
