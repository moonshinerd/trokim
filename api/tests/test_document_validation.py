"""Testes unitários da validação determinística de documentos e conciliação (Issue #89).

Cobre:
1. Cenários válidos para Fatura, Pix e Boleto (0 issues).
2. DATE_INVALID (bloqueio): datas inexistentes e datas no futuro.
3. AMOUNT_FORMAT (bloqueio): valor zero, negativo e padrão em inglês (6,000 vs 6.000).
4. TOTAL_MISMATCH (bloqueio): soma das linhas diferente do total com precisão Decimal em centavos.
5. DUE_BEFORE_ISSUE (bloqueio): vencimento anterior à emissão.
6. FIELD_MISSING (bloqueio): campos obrigatórios por tipo de documento.
7. LOW_CONFIDENCE (aviso): confiança abaixo do limiar configurado.
8. POSSIBLE_DUPLICATE (bloqueio): duplicatas com lançamentos existentes na biblioteca.
9. ALREADY_RECONCILED (bloqueio): pagamentos de fatura conciliados conforme ADR 0018.
10. Testes parametrizados e compatibilidade com dict/duck-typing.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.domain.agents import IssueSeverity
from app.domain.document import DocumentType, ExtractedDocument, ExtractedLine
from app.domain.models import (
    Account,
    AccountKind,
    Transaction,
    TransactionNature,
    TransactionType,
)
from app.services.agents.validation import ValidationIssueCode
from app.services.document_validation import (
    check_already_reconciled,
    check_amount_format,
    check_confidence,
    check_date_validity,
    check_due_before_issue,
    check_possible_duplicates,
    check_required_fields,
    check_total_mismatch,
    parse_date_safe,
    to_decimal,
    validate_document,
)
from app.services.library_service import ConfirmedTransfer, Library

# Data de referência fixa para testes determinísticos
REF_DATE = date(2026, 11, 23)


# ============================================================================
# Fixtures Sintéticas Escritas à Mão (sem dados reais - LGPD)
# ============================================================================


@pytest.fixture
def valid_fatura_synthetic() -> ExtractedDocument:
    return ExtractedDocument(
        document_type=DocumentType.FATURA,
        total_amount=Decimal("150.35"),
        currency="BRL",
        issue_date=date(2026, 10, 20),
        due_date=date(2026, 11, 5),
        institution="Banco Teste S.A.",
        account_id="banco_teste:12345",
        confidence=0.98,
        lines=[
            ExtractedLine(
                description="Padaria Central",
                amount=Decimal("30.15"),
                date=date(2026, 10, 5),
                merchant="Padaria Central",
                confidence=0.95,
            ),
            ExtractedLine(
                description="Supermercado Silva",
                amount=Decimal("120.20"),
                date=date(2026, 10, 12),
                merchant="Supermercado Silva",
                confidence=0.97,
            ),
        ],
    )


@pytest.fixture
def valid_pix_synthetic() -> ExtractedDocument:
    return ExtractedDocument(
        document_type=DocumentType.PIX,
        amount=Decimal("85.50"),
        date=date(2026, 11, 10),
        recipient="João da Silva Pereira",
        confidence=0.92,
    )


@pytest.fixture
def valid_boleto_synthetic() -> ExtractedDocument:
    return ExtractedDocument(
        document_type=DocumentType.BOLETO,
        amount=Decimal("210.00"),
        due_date=date(2026, 11, 30),
        recipient="Condomínio Residencial Parque",
        barcode="34191.79001 01043.510047 91020.150008 5 95500000021000",
        confidence=0.88,
    )


@pytest.fixture
def library_with_transactions() -> Library:
    lib = Library()
    lib.accounts["conta_corrente"] = Account(
        id="conta_corrente",
        acct_id="12345-6",
        kind=AccountKind.CHECKING,
    )
    lib.accounts["cartao_credito"] = Account(
        id="cartao_credito",
        acct_id="9999-xxxx",
        kind=AccountKind.CARD,
    )
    lib.transactions.extend(
        [
            Transaction(
                id="tx1",
                account_id="conta_corrente",
                description="Supermercado Silva",
                merchant="Supermercado Silva",
                amount=120.20,
                date=date(2026, 10, 12),
                type=TransactionType.DEBIT,
                nature=TransactionNature.PURCHASE,
            ),
            Transaction(
                id="tx2",
                account_id="conta_corrente",
                description="Pix Enviado - João da Silva",
                merchant="João da Silva",
                amount=85.50,
                date=date(2026, 11, 10),
                type=TransactionType.DEBIT,
                nature=TransactionNature.PIX_OUT,
            ),
            Transaction(
                id="tx_deb_fatura",
                account_id="conta_corrente",
                description="Pagamento de Fatura Cartão",
                amount=450.00,
                date=date(2026, 11, 8),
                type=TransactionType.DEBIT,
                nature=TransactionNature.CARD_PAYMENT,
            ),
            Transaction(
                id="tx_crd_fatura",
                account_id="cartao_credito",
                description="Pagamento Recebido",
                amount=450.00,
                date=date(2026, 11, 8),
                type=TransactionType.CREDIT,
                nature=TransactionNature.CARD_PAYMENT,
            ),
        ]
    )
    lib.confirmed["pair_fatura_450"] = ConfirmedTransfer(
        debit_uid="tx_deb_fatura",
        credit_uid="tx_crd_fatura",
        kind="pagamento_fatura",
    )
    return lib


# ============================================================================
# 1. Testes de Funções Puras Básicas: to_decimal e parse_date_safe
# ============================================================================


def test_to_decimal_various_formats() -> None:
    assert to_decimal(Decimal("100.50")) == Decimal("100.50")
    assert to_decimal(100.50) == Decimal("100.50")
    assert to_decimal(100) == Decimal("100.00")
    assert to_decimal("100.50") == Decimal("100.50")
    assert to_decimal("100,50") == Decimal("100.50")
    assert to_decimal("1.250,75") == Decimal("1250.75")
    assert to_decimal("R$ 2.450,90") == Decimal("2450.90")
    assert to_decimal("US$ 1,250.50") == Decimal("1250.50")
    assert to_decimal(None) is None
    assert to_decimal("invalido") is None


def test_parse_date_safe_formats() -> None:
    d, ok = parse_date_safe("2026-10-15")
    assert ok and d == date(2026, 10, 15)

    d, ok = parse_date_safe("15/10/2026")
    assert ok and d == date(2026, 10, 15)

    d, ok = parse_date_safe(date(2026, 10, 15))
    assert ok and d == date(2026, 10, 15)

    d, ok = parse_date_safe("2026-02-30")
    assert not ok and d is None

    d, ok = parse_date_safe(None)
    assert ok and d is None


# ============================================================================
# 2. Testes de Documentos Válidos (0 issues)
# ============================================================================


def test_valid_fatura(valid_fatura_synthetic: ExtractedDocument) -> None:
    issues = validate_document(valid_fatura_synthetic, reference_date=REF_DATE)
    assert issues == []


def test_valid_pix(valid_pix_synthetic: ExtractedDocument) -> None:
    issues = validate_document(valid_pix_synthetic, reference_date=REF_DATE)
    assert issues == []


def test_valid_boleto(valid_boleto_synthetic: ExtractedDocument) -> None:
    issues = validate_document(valid_boleto_synthetic, reference_date=REF_DATE)
    assert issues == []


# ============================================================================
# 3. DATE_INVALID (Bloqueio)
# ============================================================================


@pytest.mark.parametrize(
    "invalid_date_str",
    [
        "2026-02-30",  # dia inexistente em fevereiro
        "31/04/2026",  # abril tem 30 dias
        "32/01/2026",  # dia fora de faixa
        "data-errada",  # texto arbitrário
    ],
)
def test_date_invalid_nonexistent(invalid_date_str: str) -> None:
    doc = ExtractedDocument(
        document_type=DocumentType.PIX,
        amount=Decimal("100.00"),
        date=invalid_date_str,
        recipient="Padaria",
    )
    issues = validate_document(doc, reference_date=REF_DATE)
    date_issues = [i for i in issues if i.code == ValidationIssueCode.DATE_INVALID]
    assert len(date_issues) >= 1
    assert date_issues[0].severity == IssueSeverity.BLOCKER
    assert "inexistente ou inválida" in date_issues[0].message


def test_date_invalid_future_issue_date() -> None:
    doc = ExtractedDocument(
        document_type=DocumentType.FATURA,
        total_amount=Decimal("100.00"),
        issue_date=date(2026, 12, 1),  # Futuro em relação a REF_DATE (2026-11-23)
        due_date=date(2026, 12, 15),
        institution="Banco Teste",
    )
    issues = validate_document(doc, reference_date=REF_DATE)
    date_issues = [i for i in issues if i.code == ValidationIssueCode.DATE_INVALID]
    assert len(date_issues) >= 1
    assert date_issues[0].severity == IssueSeverity.BLOCKER
    assert "no futuro" in date_issues[0].message


def test_date_invalid_future_item_date() -> None:
    doc = ExtractedDocument(
        document_type=DocumentType.FATURA,
        total_amount=Decimal("50.00"),
        issue_date=date(2026, 10, 1),
        due_date=date(2026, 11, 1),
        institution="Banco Teste",
        lines=[
            ExtractedLine(
                description="Compra futura",
                amount=Decimal("50.00"),
                date=date(2026, 11, 28),  # Futuro em relação a REF_DATE
            )
        ],
    )
    issues = validate_document(doc, reference_date=REF_DATE)
    date_issues = [i for i in issues if i.code == ValidationIssueCode.DATE_INVALID]
    assert len(date_issues) >= 1
    assert "no futuro" in date_issues[0].message


# ============================================================================
# 4. AMOUNT_FORMAT (Bloqueio) — Incluindo Caso Obrigatório (6,000 vs 6.000)
# ============================================================================


@pytest.mark.parametrize(
    "english_amount_str",
    [
        "6,000",
        "R$ 6,000",
        "6,000.00",
        "R$ 6,000.00",
        "1,234.56",
        "10,000",
    ],
)
def test_amount_format_english_thousands_separator(english_amount_str: str) -> None:
    """Caso obrigatório mapeado no benchmark da Semana 4:

    Detectar separador de milhar no padrão em inglês (6,000) e bloquear.
    """
    doc = ExtractedDocument(
        document_type=DocumentType.PIX,
        amount=Decimal("6000.00"),
        raw_amount=english_amount_str,
        date=date(2026, 11, 1),
        recipient="Empresa Teste",
    )
    issues = validate_document(doc, reference_date=REF_DATE)
    fmt_issues = [i for i in issues if i.code == ValidationIssueCode.AMOUNT_FORMAT]
    assert len(fmt_issues) >= 1
    assert fmt_issues[0].severity == IssueSeverity.BLOCKER
    assert "padrão em inglês" in fmt_issues[0].message


@pytest.mark.parametrize(
    "ptbr_valid_amount",
    [
        "6.000",
        "6.000,00",
        "R$ 6.000,00",
        "6000",
        "6000,00",
        "R$ 6000,00",
        "1.234,56",
    ],
)
def test_amount_format_ptbr_valid_does_not_block(ptbr_valid_amount: str) -> None:
    """Valores no formato pt-BR não devem disparar AMOUNT_FORMAT."""
    doc = ExtractedDocument(
        document_type=DocumentType.PIX,
        amount=Decimal("6000.00"),
        raw_amount=ptbr_valid_amount,
        date=date(2026, 11, 1),
        recipient="Empresa Teste",
    )
    issues = validate_document(doc, reference_date=REF_DATE)
    fmt_issues = [i for i in issues if i.code == ValidationIssueCode.AMOUNT_FORMAT]
    assert fmt_issues == []


def test_amount_format_zero_value() -> None:
    doc = ExtractedDocument(
        document_type=DocumentType.BOLETO,
        amount=Decimal("0.00"),
        due_date=date(2026, 11, 30),
        recipient="Beneficiário",
    )
    issues = validate_document(doc, reference_date=REF_DATE)
    fmt_issues = [i for i in issues if i.code == ValidationIssueCode.AMOUNT_FORMAT]
    assert len(fmt_issues) >= 1
    assert fmt_issues[0].severity == IssueSeverity.BLOCKER
    assert "não pode ser zero" in fmt_issues[0].message


def test_amount_format_negative_value() -> None:
    doc = ExtractedDocument(
        document_type=DocumentType.BOLETO,
        amount=Decimal("-45.00"),
        due_date=date(2026, 11, 30),
        recipient="Beneficiário",
    )
    issues = validate_document(doc, reference_date=REF_DATE)
    fmt_issues = [i for i in issues if i.code == ValidationIssueCode.AMOUNT_FORMAT]
    assert len(fmt_issues) >= 1
    assert fmt_issues[0].severity == IssueSeverity.BLOCKER
    assert "não pode ser negativo" in fmt_issues[0].message


# ============================================================================
# 5. TOTAL_MISMATCH (Bloqueio) — Comparação Exata em Centavos com Decimal
# ============================================================================


def test_total_mismatch_exact_cents() -> None:
    doc = ExtractedDocument(
        document_type=DocumentType.FATURA,
        total_amount=Decimal("100.00"),
        issue_date=date(2026, 10, 1),
        due_date=date(2026, 10, 20),
        institution="Banco Teste",
        lines=[
            ExtractedLine(description="Item 1", amount=Decimal("49.99")),
            ExtractedLine(description="Item 2", amount=Decimal("50.00")),
            # Soma: 99.99 (diferença de 1 centavo em relação a 100.00)
        ],
    )
    issues = validate_document(doc, reference_date=REF_DATE)
    mismatch_issues = [i for i in issues if i.code == ValidationIssueCode.TOTAL_MISMATCH]
    assert len(mismatch_issues) == 1
    assert mismatch_issues[0].severity == IssueSeverity.BLOCKER
    assert "R$ 99.99" in mismatch_issues[0].message
    assert "R$ 100.00" in mismatch_issues[0].message


def test_total_matching_exact_decimal_no_float_imprecision() -> None:
    """Verifica que somas com frações decimais (ex: 0.10 + 0.20 = 0.30) não falham."""
    doc = ExtractedDocument(
        document_type=DocumentType.FATURA,
        total_amount=Decimal("0.30"),
        issue_date=date(2026, 10, 1),
        due_date=date(2026, 10, 20),
        institution="Banco Teste",
        lines=[
            ExtractedLine(description="Item 1", amount=Decimal("0.10")),
            ExtractedLine(description="Item 2", amount=Decimal("0.20")),
        ],
    )
    issues = validate_document(doc, reference_date=REF_DATE)
    mismatch_issues = [i for i in issues if i.code == ValidationIssueCode.TOTAL_MISMATCH]
    assert mismatch_issues == []


# ============================================================================
# 6. DUE_BEFORE_ISSUE (Bloqueio)
# ============================================================================


def test_due_before_issue_detected() -> None:
    doc = ExtractedDocument(
        document_type=DocumentType.FATURA,
        total_amount=Decimal("150.00"),
        issue_date=date(2026, 10, 25),
        due_date=date(2026, 10, 20),  # Vencimento antes da emissão
        institution="Banco Teste",
    )
    issues = validate_document(doc, reference_date=REF_DATE)
    due_issues = [i for i in issues if i.code == ValidationIssueCode.DUE_BEFORE_ISSUE]
    assert len(due_issues) == 1
    assert due_issues[0].severity == IssueSeverity.BLOCKER
    assert "anterior à data de emissão" in due_issues[0].message


# ============================================================================
# 7. FIELD_MISSING (Bloqueio)
# ============================================================================


def test_field_missing_fatura_institution() -> None:
    doc = ExtractedDocument(
        document_type=DocumentType.FATURA,
        total_amount=Decimal("150.00"),
        issue_date=date(2026, 10, 1),
        due_date=date(2026, 10, 20),
        institution=None,  # Ausente
    )
    issues = validate_document(doc, reference_date=REF_DATE)
    missing_issues = [i for i in issues if i.code == ValidationIssueCode.FIELD_MISSING]
    assert len(missing_issues) == 1
    assert missing_issues[0].severity == IssueSeverity.BLOCKER
    assert "instituição emissora" in missing_issues[0].message


def test_field_missing_pix_recipient() -> None:
    doc = ExtractedDocument(
        document_type=DocumentType.PIX,
        amount=Decimal("50.00"),
        date=date(2026, 10, 1),
        recipient=None,  # Ausente
    )
    issues = validate_document(doc, reference_date=REF_DATE)
    missing_issues = [i for i in issues if i.code == ValidationIssueCode.FIELD_MISSING]
    assert len(missing_issues) == 1
    assert "favorecido" in missing_issues[0].message


def test_field_missing_boleto_due_date() -> None:
    doc = ExtractedDocument(
        document_type=DocumentType.BOLETO,
        amount=Decimal("120.00"),
        due_date=None,  # Ausente
        recipient="Empresa Luz",
    )
    issues = validate_document(doc, reference_date=REF_DATE)
    missing_issues = [i for i in issues if i.code == ValidationIssueCode.FIELD_MISSING]
    assert len(missing_issues) == 1
    assert "due_date" in missing_issues[0].message


# ============================================================================
# 8. LOW_CONFIDENCE (Aviso — IssueSeverity.WARNING)
# ============================================================================


def test_low_confidence_global_warning() -> None:
    doc = ExtractedDocument(
        document_type=DocumentType.PIX,
        amount=Decimal("50.00"),
        date=date(2026, 10, 1),
        recipient="Padaria",
        confidence=0.65,  # Abaixo do padrão 0.80
    )
    issues = validate_document(doc, reference_date=REF_DATE)
    conf_issues = [i for i in issues if i.code == ValidationIssueCode.LOW_CONFIDENCE]
    assert len(conf_issues) == 1
    assert conf_issues[0].severity == IssueSeverity.WARNING
    assert "Aviso de baixa confiança" in conf_issues[0].message


def test_low_confidence_line_warning() -> None:
    doc = ExtractedDocument(
        document_type=DocumentType.FATURA,
        total_amount=Decimal("50.00"),
        issue_date=date(2026, 10, 1),
        due_date=date(2026, 10, 20),
        institution="Banco Teste",
        confidence=0.95,
        lines=[
            ExtractedLine(
                description="Item ilegível",
                amount=Decimal("50.00"),
                confidence=0.55,  # Item com baixa confiança
            )
        ],
    )
    issues = validate_document(doc, reference_date=REF_DATE)
    conf_issues = [i for i in issues if i.code == ValidationIssueCode.LOW_CONFIDENCE]
    assert len(conf_issues) == 1
    assert conf_issues[0].severity == IssueSeverity.WARNING
    assert "Item ilegível" in conf_issues[0].message


# ============================================================================
# 9. POSSIBLE_DUPLICATE (Bloqueio)
# ============================================================================


def test_possible_duplicate_matches_existing_transaction(
    library_with_transactions: Library,
) -> None:
    """Documento com mesma conta, data, valor e favorecido já presentes na biblioteca."""
    doc = ExtractedDocument(
        document_type=DocumentType.OUTRO,
        amount=Decimal("120.20"),
        date=date(2026, 10, 12),
        account_id="conta_corrente",
        recipient="Supermercado Silva",
    )
    issues = validate_document(doc, library=library_with_transactions, reference_date=REF_DATE)
    dup_issues = [i for i in issues if i.code == ValidationIssueCode.POSSIBLE_DUPLICATE]
    assert len(dup_issues) == 1
    assert dup_issues[0].severity == IssueSeverity.BLOCKER
    assert "já existe lançamento" in dup_issues[0].message


def test_possible_duplicate_does_not_fire_if_amount_differs(
    library_with_transactions: Library,
) -> None:
    doc = ExtractedDocument(
        document_type=DocumentType.OUTRO,
        amount=Decimal("120.25"),  # 5 centavos diferente
        date=date(2026, 10, 12),
        account_id="conta_corrente",
        recipient="Supermercado Silva",
    )
    issues = validate_document(doc, library=library_with_transactions, reference_date=REF_DATE)
    dup_issues = [i for i in issues if i.code == ValidationIssueCode.POSSIBLE_DUPLICATE]
    assert dup_issues == []


# ============================================================================
# 10. ALREADY_RECONCILED (Bloqueio — Conforme ADR 0018)
# ============================================================================


def test_already_reconciled_invoice_payment(library_with_transactions: Library) -> None:
    """Comprovante de pagamento de fatura que já foi conciliado como transferência própria."""
    doc = ExtractedDocument(
        document_type=DocumentType.PIX,
        amount=Decimal("450.00"),
        date=date(2026, 11, 8),
        recipient="Pagamento Fatura Cartão",
        is_invoice_payment=True,
    )
    issues = validate_document(doc, library=library_with_transactions, reference_date=REF_DATE)
    rec_issues = [i for i in issues if i.code == ValidationIssueCode.ALREADY_RECONCILED]
    assert len(rec_issues) == 1
    assert rec_issues[0].severity == IssueSeverity.BLOCKER
    assert "já foi conciliado" in rec_issues[0].message


def test_already_reconciled_within_3_days_window(
    library_with_transactions: Library,
) -> None:
    """Janela de conciliação de 3 dias definida na ADR 0018."""
    # Data 2026-11-10 está a 2 dias de tx_deb_fatura (2026-11-08) -> dentro da janela de 3 dias
    doc = ExtractedDocument(
        document_type=DocumentType.FATURA,
        total_amount=Decimal("450.00"),
        due_date=date(2026, 11, 10),
        issue_date=date(2026, 10, 20),
        institution="Cartão Teste",
        is_invoice_payment=True,
    )
    issues = validate_document(doc, library=library_with_transactions, reference_date=REF_DATE)
    rec_issues = [i for i in issues if i.code == ValidationIssueCode.ALREADY_RECONCILED]
    assert len(rec_issues) == 1
    assert rec_issues[0].severity == IssueSeverity.BLOCKER


def test_not_reconciled_outside_3_days_window(
    library_with_transactions: Library,
) -> None:
    # Data 2026-11-15 está a 7 dias de tx_deb_fatura (2026-11-08) -> fora da janela de 3 dias
    doc = ExtractedDocument(
        document_type=DocumentType.FATURA,
        total_amount=Decimal("450.00"),
        due_date=date(2026, 11, 15),
        issue_date=date(2026, 10, 20),
        institution="Cartão Teste",
        is_invoice_payment=True,
    )
    issues = validate_document(doc, library=library_with_transactions, reference_date=REF_DATE)
    rec_issues = [i for i in issues if i.code == ValidationIssueCode.ALREADY_RECONCILED]
    assert rec_issues == []


# ============================================================================
# 12. Testes Diretos das Funções Puras Isoladas
# ============================================================================


def test_isolated_check_amount_format() -> None:
    doc_bad = ExtractedDocument(amount="R$ 6,000")
    assert len(check_amount_format(doc_bad)) == 1

    doc_good = ExtractedDocument(amount="R$ 6.000,00")
    assert check_amount_format(doc_good) == []


def test_isolated_check_date_validity() -> None:
    doc_bad = ExtractedDocument(issue_date="2026-02-30")
    assert len(check_date_validity(doc_bad, reference_date=REF_DATE)) == 1

    doc_good = ExtractedDocument(issue_date="2026-10-15")
    assert check_date_validity(doc_good, reference_date=REF_DATE) == []


def test_isolated_check_due_before_issue() -> None:
    doc_bad = ExtractedDocument(issue_date="2026-10-15", due_date="2026-10-10")
    assert len(check_due_before_issue(doc_bad)) == 1

    doc_good = ExtractedDocument(issue_date="2026-10-15", due_date="2026-10-20")
    assert check_due_before_issue(doc_good) == []


def test_isolated_check_total_mismatch() -> None:
    doc_bad = ExtractedDocument(
        total_amount=Decimal("100.00"),
        lines=[ExtractedLine(amount=Decimal("50.00")), ExtractedLine(amount=Decimal("49.00"))],
    )
    assert len(check_total_mismatch(doc_bad)) == 1

    doc_good = ExtractedDocument(
        total_amount=Decimal("100.00"),
        lines=[ExtractedLine(amount=Decimal("50.00")), ExtractedLine(amount=Decimal("50.00"))],
    )
    assert check_total_mismatch(doc_good) == []


def test_isolated_check_required_fields() -> None:
    doc_bad = ExtractedDocument(document_type=DocumentType.FATURA)
    assert len(check_required_fields(doc_bad)) >= 3

    doc_good = ExtractedDocument(
        document_type=DocumentType.PIX,
        amount=Decimal("10.00"),
        date="2026-10-10",
        recipient="Maria",
    )
    assert check_required_fields(doc_good) == []


def test_isolated_check_confidence() -> None:
    doc_low = ExtractedDocument(confidence=0.5)
    assert len(check_confidence(doc_low, confidence_threshold=0.8)) == 1

    doc_high = ExtractedDocument(confidence=0.9)
    assert check_confidence(doc_high, confidence_threshold=0.8) == []


def test_isolated_check_possible_duplicates(library_with_transactions: Library) -> None:
    doc = ExtractedDocument(
        amount=Decimal("120.20"),
        date=date(2026, 10, 12),
        account_id="conta_corrente",
        recipient="Supermercado Silva",
    )
    assert len(check_possible_duplicates(doc, library=library_with_transactions)) == 1


def test_isolated_check_already_reconciled(library_with_transactions: Library) -> None:
    doc = ExtractedDocument(
        document_type=DocumentType.FATURA,
        total_amount=Decimal("450.00"),
        due_date=date(2026, 11, 8),
        is_invoice_payment=True,
    )
    assert len(check_already_reconciled(doc, library=library_with_transactions)) == 1


def test_validate_document_from_dict() -> None:
    doc_dict = {
        "document_type": "pix",
        "amount": "100,50",
        "date": "2026-11-10",
        "recipient": "Farmácia Popular",
        "confidence": 0.95,
    }
    issues = validate_document(doc_dict, reference_date=REF_DATE)
    assert issues == []


def test_validate_document_multiple_simultaneous_issues() -> None:
    """Documento com múltiplos problemas simultâneos:

    Data no futuro + valor zero + campo ausente + baixa confiança.
    """
    doc_dict = {
        "document_type": "pix",
        "amount": 0.0,  # AMOUNT_FORMAT
        "date": "2026-12-25",  # DATE_INVALID (futuro)
        "recipient": None,  # FIELD_MISSING
        "confidence": 0.40,  # LOW_CONFIDENCE (aviso)
    }
    issues = validate_document(doc_dict, reference_date=REF_DATE)
    codes = {i.code for i in issues}
    assert ValidationIssueCode.AMOUNT_FORMAT in codes
    assert ValidationIssueCode.DATE_INVALID in codes
    assert ValidationIssueCode.FIELD_MISSING in codes
    assert ValidationIssueCode.LOW_CONFIDENCE in codes

    blockers = [i for i in issues if i.severity == IssueSeverity.BLOCKER]
    warnings = [i for i in issues if i.severity == IssueSeverity.WARNING]
    assert len(blockers) == 3
    assert len(warnings) == 1
