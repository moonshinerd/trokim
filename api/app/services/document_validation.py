"""Validação determinística de campos extraídos de documentos e conciliação com a biblioteca.

Implementa a Issue #89 (pertencente ao Épico #86 — Semana 5: Multimodalidade).
Regras em total conformidade com:
- AGENTS.md: funções puras, sem LLM, sem acesso à rede, mensagens em pt-BR.
- ADR 0004: cálculos determinísticos com decimal.Decimal para precisão monetária em centavos.
- ADR 0016: separação estrita do ValidationAgent e reutilização de ValidationIssue.
- ADR 0018: conciliação de transferências e pagamentos de fatura de cartão (janela de 3 dias).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.agents import IssueSeverity, ValidationIssue
from app.domain.document import DocumentType, ExtractedDocument, ExtractedLine
from app.domain.models import TransactionNature
from app.services.agents.validation import ValidationIssueCode
from app.services.library_service import Library
from app.services.statement_profiles import normalize_text
from app.services.transfer_service import name_matches

# Janela de conciliação de pagamento de fatura conforme ADR 0018 (_PAYMENT_WINDOW_DAYS = 3)
PAYMENT_WINDOW_DAYS = 3

# Padrão para detecção de separador de milhar no padrão em inglês
# (ex.: 6,000, 6,000.00, R$ 6,000, 1,234.56). Em pt-BR, vírgula é separador decimal.
ENGLISH_THOUSANDS_PATTERN = re.compile(
    r"(?:[^\d]|^)\d{1,3}(?:,\d{3})+(?:\.\d{2})?(?:[^\d]|$)|(?:[^\d]|^)\d+,\d{3}(?:[^\d]|$)"
)


def to_decimal(val: Any) -> Decimal | None:
    """Converte um valor monetário para Decimal quantizado em centavos (2 casas).

    NUNCA realiza aritmética em float.
    Suporta float, int, str com formatação pt-BR ("1.250,50") ou internacional ("1250.50").
    """
    if val is None or val == "":
        return None
    if isinstance(val, Decimal):
        return val.quantize(Decimal("0.01"))
    if isinstance(val, (int, float)):
        # Arredondamento seguro de 2 casas antes de instanciar Decimal
        return Decimal(f"{val:.2f}").quantize(Decimal("0.01"))
    if isinstance(val, str):
        cleaned = (
            val.strip()
            .replace("R$", "")
            .replace("US$", "")
            .replace("USD", "")
            .replace("$", "")
            .strip()
        )
        if not cleaned:
            return None
        # Tratamento de separadores
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                # Formato pt-BR: 1.250,50 -> 1250.50
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                # Formato en-US: 1,250.50 -> 1250.50
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        try:
            return Decimal(cleaned).quantize(Decimal("0.01"))
        except InvalidOperation:
            return None
    return None


def parse_date_safe(val: Any) -> tuple[date | None, bool]:
    """Valida e converte um valor para datetime.date.

    Retorna tupla: (data_parseada, eh_valida).
    - Se val for None ou vazio: (None, True).
    - Se for data inexistente ou formato inválido (ex.: '2026-02-30'): (None, False).
    """
    if val is None or val == "":
        return None, True
    if isinstance(val, date) and not isinstance(val, datetime):
        return val, True
    if isinstance(val, datetime):
        return val.date(), True
    if isinstance(val, str):
        s = val.strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(s, fmt).date(), True
            except ValueError:
                continue
        return None, False
    return None, False


def _get_doc(doc: Any) -> ExtractedDocument:
    """Garante instância de ExtractedDocument a partir de dict, modelo ou objeto duck-typed."""
    if isinstance(doc, ExtractedDocument):
        return doc
    if isinstance(doc, dict):
        return ExtractedDocument.model_validate(doc)
    # Objeto genérico
    lines: list[ExtractedLine] = []
    raw_lines = getattr(doc, "lines", []) or []
    for item in raw_lines:
        if isinstance(item, ExtractedLine):
            lines.append(item)
        elif isinstance(item, dict):
            lines.append(ExtractedLine.model_validate(item))
        else:
            lines.append(
                ExtractedLine(
                    description=getattr(item, "description", ""),
                    amount=getattr(item, "amount", Decimal("0.00")),
                    raw_amount=getattr(item, "raw_amount", None),
                    date=getattr(item, "date", None),
                    category=getattr(item, "category", None),
                    merchant=getattr(item, "merchant", None),
                    confidence=getattr(item, "confidence", None),
                )
            )
    return ExtractedDocument(
        document_type=getattr(doc, "document_type", DocumentType.OUTRO),
        total_amount=getattr(doc, "total_amount", None),
        amount=getattr(doc, "amount", None),
        raw_amount=getattr(doc, "raw_amount", None),
        currency=getattr(doc, "currency", "BRL"),
        date=getattr(doc, "date", None),
        issue_date=getattr(doc, "issue_date", None),
        due_date=getattr(doc, "due_date", None),
        recipient=getattr(doc, "recipient", None),
        sender=getattr(doc, "sender", None),
        merchant=getattr(doc, "merchant", None),
        institution=getattr(doc, "institution", None),
        account_id=getattr(doc, "account_id", None),
        barcode=getattr(doc, "barcode", None),
        confidence=getattr(doc, "confidence", None),
        lines=lines,
        is_invoice_payment=getattr(doc, "is_invoice_payment", False),
        raw_text=getattr(doc, "raw_text", None),
    )


def check_amount_format(doc: ExtractedDocument) -> list[ValidationIssue]:
    """Regra AMOUNT_FORMAT (bloqueio).

    Verifica valor zero, negativo onde não cabe, ou erro de separador (ex.: R$ 6,000).
    """
    issues: list[ValidationIssue] = []

    # 1. Checagem de formato em inglês (separador milhar com vírgula)
    raw_candidates = [doc.raw_amount]
    if isinstance(doc.amount, str):
        raw_candidates.append(doc.amount)
    if isinstance(doc.total_amount, str):
        raw_candidates.append(doc.total_amount)
    for line in doc.lines:
        raw_candidates.append(line.raw_amount)
        if isinstance(line.amount, str):
            raw_candidates.append(line.amount)

    for raw in raw_candidates:
        if raw and ENGLISH_THOUSANDS_PATTERN.search(raw):
            issues.append(
                ValidationIssue(
                    code=ValidationIssueCode.AMOUNT_FORMAT,
                    severity=IssueSeverity.BLOCKER,
                    message=(
                        f"Formato de valor inválido: detectado separador de milhar no padrão em "
                        f"inglês ('{raw}'). O formato exigido é pt-BR (ex.: 'R$ 6.000,00')."
                    ),
                )
            )
            # Uma falha de padrão em inglês é suficiente para o bloqueio desse tipo
            break

    # 2. Checagem de valor zero ou negativo no total do documento
    doc_amount = to_decimal(doc.total_amount if doc.total_amount is not None else doc.amount)
    if doc_amount is not None:
        if doc_amount == Decimal("0.00"):
            issues.append(
                ValidationIssue(
                    code=ValidationIssueCode.AMOUNT_FORMAT,
                    severity=IssueSeverity.BLOCKER,
                    message="Valor inválido: o valor do documento não pode ser zero (R$ 0,00).",
                )
            )
        elif doc_amount < Decimal("0.00"):
            issues.append(
                ValidationIssue(
                    code=ValidationIssueCode.AMOUNT_FORMAT,
                    severity=IssueSeverity.BLOCKER,
                    message=(
                        f"Valor inválido: o valor total do documento não pode ser negativo "
                        f"(R$ {doc_amount:.2f})."
                    ),
                )
            )
    elif (doc.total_amount is not None or doc.amount is not None) and not issues:
        # Valor fornecido mas inválido para conversão decimal
        issues.append(
            ValidationIssue(
                code=ValidationIssueCode.AMOUNT_FORMAT,
                severity=IssueSeverity.BLOCKER,
                message="Valor monetário inválido ou não numérico.",
            )
        )

    return issues


def check_date_validity(
    doc: ExtractedDocument, reference_date: date | None = None
) -> list[ValidationIssue]:
    """Regra DATE_INVALID (bloqueio).

    Verifica data inexistente (ex.: 30 de fevereiro) ou no futuro em relação à data de referência.
    """
    ref_date = reference_date or date.today()
    issues: list[ValidationIssue] = []

    # Checa data de emissão
    p_issue, ok_issue = parse_date_safe(doc.issue_date)
    if not ok_issue:
        issues.append(
            ValidationIssue(
                code=ValidationIssueCode.DATE_INVALID,
                severity=IssueSeverity.BLOCKER,
                message=f"Data de emissão inexistente ou inválida: '{doc.issue_date}'.",
            )
        )
    elif p_issue and p_issue > ref_date:
        issues.append(
            ValidationIssue(
                code=ValidationIssueCode.DATE_INVALID,
                severity=IssueSeverity.BLOCKER,
                message=(
                    f"Data de emissão no futuro: {p_issue.isoformat()} "
                    f"(data de referência: {ref_date.isoformat()})."
                ),
            )
        )

    # Checa data principal / transação
    p_date, ok_date = parse_date_safe(doc.date)
    if not ok_date:
        issues.append(
            ValidationIssue(
                code=ValidationIssueCode.DATE_INVALID,
                severity=IssueSeverity.BLOCKER,
                message=f"Data do documento inexistente ou inválida: '{doc.date}'.",
            )
        )
    elif p_date and p_date > ref_date:
        issues.append(
            ValidationIssue(
                code=ValidationIssueCode.DATE_INVALID,
                severity=IssueSeverity.BLOCKER,
                message=(
                    f"Data do documento no futuro: {p_date.isoformat()} "
                    f"(data de referência: {ref_date.isoformat()})."
                ),
            )
        )

    # Checa data de vencimento (vencimento no futuro é permitido, mas data inexistente não)
    p_due, ok_due = parse_date_safe(doc.due_date)
    if not ok_due:
        issues.append(
            ValidationIssue(
                code=ValidationIssueCode.DATE_INVALID,
                severity=IssueSeverity.BLOCKER,
                message=f"Data de vencimento inexistente ou inválida: '{doc.due_date}'.",
            )
        )

    # Checa datas dos itens da fatura
    for idx, line in enumerate(doc.lines, start=1):
        if line.date:
            p_line, ok_line = parse_date_safe(line.date)
            if not ok_line:
                issues.append(
                    ValidationIssue(
                        code=ValidationIssueCode.DATE_INVALID,
                        severity=IssueSeverity.BLOCKER,
                        message=(
                            f"Data inexistente ou inválida no item {idx} "
                            f"('{line.description}'): '{line.date}'."
                        ),
                    )
                )
            elif p_line and p_line > ref_date:
                issues.append(
                    ValidationIssue(
                        code=ValidationIssueCode.DATE_INVALID,
                        severity=IssueSeverity.BLOCKER,
                        message=(
                            f"Data do item {idx} ('{line.description}') no futuro: "
                            f"{p_line.isoformat()}."
                        ),
                    )
                )

    return issues


def check_due_before_issue(doc: ExtractedDocument) -> list[ValidationIssue]:
    """Regra DUE_BEFORE_ISSUE (bloqueio).

    Verifica se a data de vencimento é anterior à data de emissão.
    """
    issues: list[ValidationIssue] = []
    p_due, ok_due = parse_date_safe(doc.due_date)
    p_issue, ok_issue = parse_date_safe(doc.issue_date or doc.date)

    if ok_due and ok_issue and p_due and p_issue:
        if p_due < p_issue:
            issues.append(
                ValidationIssue(
                    code=ValidationIssueCode.DUE_BEFORE_ISSUE,
                    severity=IssueSeverity.BLOCKER,
                    message=(
                        f"Inconsistência de datas: data de vencimento ({p_due.isoformat()}) "
                        f"é anterior à data de emissão ({p_issue.isoformat()})."
                    ),
                )
            )
    return issues


def check_total_mismatch(doc: ExtractedDocument) -> list[ValidationIssue]:
    """Regra TOTAL_MISMATCH (bloqueio).

    Verifica se a soma das linhas difere do total da fatura.
    Todas as somas e comparações usam estritamente Decimal quantizado em centavos (ADR 0004).
    """
    issues: list[ValidationIssue] = []
    if not doc.lines:
        return issues

    expected_total = to_decimal(doc.total_amount if doc.total_amount is not None else doc.amount)
    if expected_total is None:
        return issues

    lines_sum = sum(
        (to_decimal(line.amount) or Decimal("0.00") for line in doc.lines),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))

    if lines_sum != expected_total:
        issues.append(
            ValidationIssue(
                code=ValidationIssueCode.TOTAL_MISMATCH,
                severity=IssueSeverity.BLOCKER,
                message=(
                    f"Divergência de valores: a soma dos itens da fatura (R$ {lines_sum:.2f}) "
                    f"difere do total informado (R$ {expected_total:.2f})."
                ),
            )
        )

    return issues


def check_required_fields(doc: ExtractedDocument) -> list[ValidationIssue]:
    """Regra FIELD_MISSING (bloqueio).

    Verifica campos obrigatórios conforme o tipo de documento.
    """
    issues: list[ValidationIssue] = []
    dtype = str(doc.document_type).lower()

    if dtype in (DocumentType.FATURA, "fatura", "invoice", "cartao"):
        if doc.total_amount is None and doc.amount is None:
            issues.append(
                ValidationIssue(
                    code=ValidationIssueCode.FIELD_MISSING,
                    severity=IssueSeverity.BLOCKER,
                    message="Campo obrigatório ausente para fatura: valor total (total_amount).",
                )
            )
        if not doc.issue_date and not doc.date:
            issues.append(
                ValidationIssue(
                    code=ValidationIssueCode.FIELD_MISSING,
                    severity=IssueSeverity.BLOCKER,
                    message="Campo obrigatório ausente para fatura: data de emissão (issue_date).",
                )
            )
        if not doc.due_date:
            issues.append(
                ValidationIssue(
                    code=ValidationIssueCode.FIELD_MISSING,
                    severity=IssueSeverity.BLOCKER,
                    message="Campo obrigatório ausente para fatura: data de vencimento (due_date).",
                )
            )
        if not doc.institution and not doc.merchant:
            issues.append(
                ValidationIssue(
                    code=ValidationIssueCode.FIELD_MISSING,
                    severity=IssueSeverity.BLOCKER,
                    message=(
                        "Campo obrigatório ausente para fatura: instituição emissora (institution)."
                    ),
                )
            )

    elif dtype in (DocumentType.PIX, "pix", "comprovante_pix"):
        if doc.amount is None and doc.total_amount is None:
            issues.append(
                ValidationIssue(
                    code=ValidationIssueCode.FIELD_MISSING,
                    severity=IssueSeverity.BLOCKER,
                    message="Campo obrigatório ausente para comprovante de Pix: valor (amount).",
                )
            )
        if not doc.date and not doc.issue_date:
            issues.append(
                ValidationIssue(
                    code=ValidationIssueCode.FIELD_MISSING,
                    severity=IssueSeverity.BLOCKER,
                    message="Campo obrigatório ausente para comprovante de Pix: data (date).",
                )
            )
        if not doc.recipient and not doc.merchant:
            issues.append(
                ValidationIssue(
                    code=ValidationIssueCode.FIELD_MISSING,
                    severity=IssueSeverity.BLOCKER,
                    message=(
                        "Campo obrigatório ausente para comprovante de Pix: favorecido (recipient)."
                    ),
                )
            )

    elif dtype in (DocumentType.BOLETO, "boleto", "boleto_bancario"):
        if doc.amount is None and doc.total_amount is None:
            issues.append(
                ValidationIssue(
                    code=ValidationIssueCode.FIELD_MISSING,
                    severity=IssueSeverity.BLOCKER,
                    message="Campo obrigatório ausente para boleto: valor (amount).",
                )
            )
        if not doc.due_date:
            issues.append(
                ValidationIssue(
                    code=ValidationIssueCode.FIELD_MISSING,
                    severity=IssueSeverity.BLOCKER,
                    message="Campo obrigatório ausente para boleto: data de vencimento (due_date).",
                )
            )
        if not doc.recipient and not doc.barcode and not doc.merchant:
            issues.append(
                ValidationIssue(
                    code=ValidationIssueCode.FIELD_MISSING,
                    severity=IssueSeverity.BLOCKER,
                    message=(
                        "Campo obrigatório ausente para boleto: beneficiário ou código de barras."
                    ),
                )
            )

    else:
        # Documento genérico / outro
        if doc.amount is None and doc.total_amount is None:
            issues.append(
                ValidationIssue(
                    code=ValidationIssueCode.FIELD_MISSING,
                    severity=IssueSeverity.BLOCKER,
                    message="Campo obrigatório ausente: valor monetário (amount).",
                )
            )
        if not doc.date and not doc.issue_date:
            issues.append(
                ValidationIssue(
                    code=ValidationIssueCode.FIELD_MISSING,
                    severity=IssueSeverity.BLOCKER,
                    message="Campo obrigatório ausente: data do documento (date).",
                )
            )

    return issues


def check_confidence(
    doc: ExtractedDocument, confidence_threshold: float = 0.80
) -> list[ValidationIssue]:
    """Regra LOW_CONFIDENCE (aviso).

    Destaca na revisão casos em que a confiança da extração ficou abaixo do limiar configurado.
    Não bloqueia a confirmação automática por si só, apenas sinaliza alerta.
    """
    issues: list[ValidationIssue] = []

    if doc.confidence is not None and doc.confidence < confidence_threshold:
        issues.append(
            ValidationIssue(
                code=ValidationIssueCode.LOW_CONFIDENCE,
                severity=IssueSeverity.WARNING,
                message=(
                    f"Aviso de baixa confiança: a confiança global ({doc.confidence:.2f}) "
                    f"está abaixo do limiar ({confidence_threshold:.2f})."
                ),
            )
        )

    for idx, line in enumerate(doc.lines, start=1):
        if line.confidence is not None and line.confidence < confidence_threshold:
            issues.append(
                ValidationIssue(
                    code=ValidationIssueCode.LOW_CONFIDENCE,
                    severity=IssueSeverity.WARNING,
                    message=(
                        f"Aviso de baixa confiança no item {idx} ('{line.description}'): "
                        f"confiança ({line.confidence:.2f}) abaixo do limiar "
                        f"({confidence_threshold:.2f})."
                    ),
                )
            )

    return issues


def check_possible_duplicates(
    doc: ExtractedDocument, library: Library | None
) -> list[ValidationIssue]:
    """Regra POSSIBLE_DUPLICATE (bloqueio).

    Compara conta, data, valor (em centavos com Decimal) e favorecido contra os lançamentos
    já existentes na biblioteca do usuário.
    """
    if not library or not library.transactions:
        return []

    issues: list[ValidationIssue] = []

    # Determina itens a verificar: se houver linhas na fatura, checa cada linha; senão checa o doc
    items_to_check: list[dict[str, Any]] = []
    if doc.lines:
        for idx, line in enumerate(doc.lines, start=1):
            p_date, _ = parse_date_safe(line.date or doc.date or doc.issue_date)
            items_to_check.append(
                {
                    "item_desc": f"item {idx} ('{line.description}')",
                    "amount": to_decimal(line.amount),
                    "date": p_date,
                    "payee": line.merchant or line.description or doc.recipient or doc.merchant,
                    "account_id": doc.account_id,
                }
            )
    else:
        p_date, _ = parse_date_safe(doc.date or doc.issue_date)
        doc_amt = to_decimal(doc.total_amount if doc.total_amount is not None else doc.amount)
        items_to_check.append(
            {
                "item_desc": "documento",
                "amount": doc_amt,
                "date": p_date,
                "payee": doc.recipient or doc.merchant,
                "account_id": doc.account_id,
            }
        )

    for cand in items_to_check:
        cand_amount = cand["amount"]
        cand_date = cand["date"]
        cand_payee = cand["payee"]
        cand_acc = cand["account_id"]

        if cand_amount is None or cand_date is None or not cand_payee:
            continue

        cand_payee_norm = normalize_text(cand_payee)

        for tx in library.transactions:
            # 1. Conta (se informada no documento)
            if cand_acc and tx.account_id != cand_acc:
                continue

            # 2. Data exata
            if tx.date != cand_date:
                continue

            # 3. Valor em centavos exatos via Decimal
            tx_amount = to_decimal(tx.amount)
            if tx_amount != cand_amount:
                continue

            # 4. Favorecido / estabelecimento
            tx_merchant = tx.merchant or tx.description
            tx_payee_norm = normalize_text(tx_merchant)

            is_match = (
                cand_payee_norm == tx_payee_norm
                or name_matches(cand_payee, tx_merchant)
                or (len(cand_payee_norm) >= 4 and cand_payee_norm in tx_payee_norm)
                or (len(tx_payee_norm) >= 4 and tx_payee_norm in cand_payee_norm)
            )

            if is_match:
                issues.append(
                    ValidationIssue(
                        code=ValidationIssueCode.POSSIBLE_DUPLICATE,
                        severity=IssueSeverity.BLOCKER,
                        message=(
                            f"Possível duplicata ({cand['item_desc']}): já existe lançamento "
                            f"na conta '{tx.account_id}' em {tx.date.isoformat()} no valor de "
                            f"R$ {tx_amount:.2f} para '{tx_merchant}'."
                        ),
                    )
                )
                break  # Encontrou duplicata para este item, passa para o próximo

    return issues


def check_already_reconciled(
    doc: ExtractedDocument, library: Library | None
) -> list[ValidationIssue]:
    """Regra ALREADY_RECONCILED (bloqueio).

    Seguindo estritamente a ADR 0018: detecta pagamento de fatura que já foi reconhecido
    e conciliado como transferência na biblioteca (pares de 'pagamento_fatura' ou lançamentos
    com nature CARD_PAYMENT na janela de até 3 dias).
    """
    if not library:
        return []

    dtype = str(doc.document_type).lower()
    is_invoice_doc = dtype in (DocumentType.FATURA, "fatura", "cartao")
    doc_text = f"{doc.raw_text or ''} {doc.recipient or ''} {doc.merchant or ''}".lower()
    mentions_invoice_payment = (
        doc.is_invoice_payment
        or "pagamento de fatura" in doc_text
        or "pagamento fatura" in doc_text
        or "pagamento cartao" in doc_text
        or "pagamento cartão" in doc_text
        or "fatura paga" in doc_text
    )

    if not is_invoice_doc and not mentions_invoice_payment:
        return []

    doc_amount = to_decimal(doc.total_amount if doc.total_amount is not None else doc.amount)
    p_date, _ = parse_date_safe(doc.date or doc.due_date or doc.issue_date)

    if doc_amount is None or p_date is None:
        return []

    by_uid = {tx.uid: tx for tx in library.transactions}
    by_id = {tx.id: tx for tx in library.transactions if tx.id}

    # 1. Verifica transferências confirmadas de 'pagamento_fatura' (ADR 0018)
    for transfer in library.confirmed.values():
        if transfer.kind == "pagamento_fatura":
            debit = by_uid.get(transfer.debit_uid) or by_id.get(transfer.debit_uid)
            credit = by_uid.get(transfer.credit_uid) or by_id.get(transfer.credit_uid)
            for t in (debit, credit):
                if t is not None:
                    t_amt = to_decimal(t.amount)
                    if t_amt == doc_amount and abs((t.date - p_date).days) <= PAYMENT_WINDOW_DAYS:
                        return [
                            ValidationIssue(
                                code=ValidationIssueCode.ALREADY_RECONCILED,
                                severity=IssueSeverity.BLOCKER,
                                message=(
                                    f"Pagamento de fatura já conciliado: lançamento de "
                                    f"R$ {doc_amount:.2f} próximo a {p_date.isoformat()} já foi "
                                    f"conciliado como transferência própria entre contas "
                                    f"(ADR 0018)."
                                ),
                            )
                        ]

    # 2. Verifica lançamentos marcados com natureza CARD_PAYMENT
    for tx in library.transactions:
        if tx.nature == TransactionNature.CARD_PAYMENT:
            tx_amt = to_decimal(tx.amount)
            if tx_amt == doc_amount and abs((tx.date - p_date).days) <= PAYMENT_WINDOW_DAYS:
                return [
                    ValidationIssue(
                        code=ValidationIssueCode.ALREADY_RECONCILED,
                        severity=IssueSeverity.BLOCKER,
                        message=(
                            f"Pagamento de fatura já conciliado: lançamento de R$ {doc_amount:.2f} "
                            f"em {tx.date.isoformat()} já foi conciliado como pagamento "
                            f"de fatura (ADR 0018)."
                        ),
                    )
                ]

    return []


def validate_document(
    doc: Any,
    library: Library | None = None,
    *,
    confidence_threshold: float = 0.80,
    reference_date: date | None = None,
) -> list[ValidationIssue]:
    """Função pura que valida os campos de um documento extraído e concilia com a biblioteca.

    Retorna lista de ValidationIssue, distinguindo com precisão:
    - Bloqueios (IssueSeverity.BLOCKER): impedem confirmação automática.
    - Avisos (IssueSeverity.WARNING): apenas destacam alertas para revisão humana.

    Parâmetros:
        doc: ExtractedDocument, dicionário ou objeto com os campos extraídos.
        library: Biblioteca opcional da sessão (com lançamentos e transferências para conciliação).
        confidence_threshold: Limiar de confiança para emissão de avisos (padrão: 0.80).
        reference_date: Data base para checagem de datas futuras (padrão: date.today()).
    """
    extracted = _get_doc(doc)
    issues: list[ValidationIssue] = []

    # 1. DATE_INVALID (bloqueio)
    issues.extend(check_date_validity(extracted, reference_date=reference_date))

    # 2. AMOUNT_FORMAT (bloqueio)
    issues.extend(check_amount_format(extracted))

    # 3. TOTAL_MISMATCH (bloqueio)
    issues.extend(check_total_mismatch(extracted))

    # 4. DUE_BEFORE_ISSUE (bloqueio)
    issues.extend(check_due_before_issue(extracted))

    # 5. FIELD_MISSING (bloqueio)
    issues.extend(check_required_fields(extracted))

    # 6. LOW_CONFIDENCE (aviso)
    issues.extend(check_confidence(extracted, confidence_threshold=confidence_threshold))

    # 7. POSSIBLE_DUPLICATE (bloqueio)
    issues.extend(check_possible_duplicates(extracted, library=library))

    # 8. ALREADY_RECONCILED (bloqueio)
    issues.extend(check_already_reconciled(extracted, library=library))

    return issues
