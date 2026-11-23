"""Ponte agente de documento (#88) -> validação (#89): o resultado do agente é validável."""

from datetime import date
from decimal import Decimal

from app.domain.agents import IssueSeverity
from app.domain.document import DocumentType
from app.domain.documents import (
    DocumentKind,
    DocumentQuality,
    ExtractedField,
    ExtractedTransaction,
    FieldSource,
    QualityReport,
)
from app.domain.documents import ExtractedDocument as AgentDocument
from app.services.document_adapter import from_agent_document
from app.services.document_validation import validate_document


def _field(key, value, confidence=0.95):
    return ExtractedField(key=key, value=value, confidence=confidence, source=FieldSource.OCR)


def _agent_doc(kind, fields, transactions=()):
    return AgentDocument(
        kind=kind,
        bank=None,
        quality=QualityReport(
            quality=DocumentQuality.LEGIBLE,
            sharpness=100.0,
            resolution=(900, 600),
            mean_ocr_confidence=0.95,
            reasons=[],
        ),
        fields=fields,
        transactions=list(transactions),
        abstained=False,
        reason=None,
        engine="mock",
    )


def _codes(issues, severity=None):
    return {i.code for i in issues if severity is None or i.severity == severity}


def test_converte_tipo_campos_e_linhas():
    doc = _agent_doc(
        DocumentKind.CARD_INVOICE,
        [
            _field("total", "150.00", 0.9),
            _field("date", "2026-11-01"),
            _field("due_date", "2026-11-10"),
            _field("bank", "Banco Fictício"),
        ],
        [
            ExtractedTransaction(
                date=date(2026, 10, 20), description="Mercado", amount=100.0, confidence=0.9
            ),
            ExtractedTransaction(
                date=date(2026, 10, 21), description="Farmácia", amount=50.0, confidence=0.8
            ),
        ],
    )
    out = from_agent_document(doc)
    assert out.document_type == DocumentType.FATURA
    assert out.total_amount == Decimal("150.00")
    assert str(out.due_date) == "2026-11-10"
    assert out.institution == "Banco Fictício"
    assert [line.amount for line in out.lines] == [Decimal("100.00"), Decimal("50.00")]
    assert out.confidence == 0.8  # a menor confiança, não a média


def test_campo_ausente_continua_ausente():
    out = from_agent_document(_agent_doc(DocumentKind.PIX_RECEIPT, [_field("amount", "10.00")]))
    assert out.document_type == DocumentType.PIX
    assert out.date is None and out.recipient is None


def test_validacao_aceita_a_saida_do_agente_diretamente():
    ok = _agent_doc(
        DocumentKind.CARD_INVOICE,
        [
            _field("bank", "Banco Fictício"),
            _field("total", "150.00"),
            _field("date", "2026-11-01"),
            _field("due_date", "2026-11-10"),
        ],
        [
            ExtractedTransaction(
                date=date(2026, 10, 20), description="A", amount=100.0, confidence=0.9
            ),
            ExtractedTransaction(
                date=date(2026, 10, 21), description="B", amount=50.0, confidence=0.9
            ),
        ],
    )
    assert _codes(validate_document(ok), IssueSeverity.BLOCKER) == set()


def test_validacao_barra_fatura_cuja_soma_nao_fecha():
    bad = _agent_doc(
        DocumentKind.CARD_INVOICE,
        [_field("total", "150.00"), _field("date", "2026-11-01"), _field("due_date", "2026-11-10")],
        [
            ExtractedTransaction(
                date=date(2026, 10, 20), description="A", amount=100.0, confidence=0.9
            )
        ],
    )
    assert "TOTAL_MISMATCH" in _codes(validate_document(bad), IssueSeverity.BLOCKER)


def test_validacao_barra_pix_sem_campos_obrigatorios():
    vazio = _agent_doc(DocumentKind.PIX_RECEIPT, [])
    assert "FIELD_MISSING" in _codes(validate_document(vazio), IssueSeverity.BLOCKER)
