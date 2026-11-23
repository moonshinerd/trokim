"""Reprodução, privacidade, gabarito e abstenção do corpus multimodal da #90."""

import copy
import io
import json
from collections import Counter
from unittest.mock import AsyncMock

import pytest
from jsonschema import Draft202012Validator, ValidationError
from pypdf import PdfReader
from rag_benchmark.calibrate_documents import calibrate, image_metrics, summarize
from rag_benchmark.document_dataset import ROOT, SCHEMA, load_dataset
from synthetic_data.generate_document_images import NAMES, PERSONAL, build, manifest

from app.domain.documents import DocumentQuality, ExtractedField, ExtractedTransaction, FieldSource
from app.services.agents.document import DocumentAgent, DocumentContext
from app.services.image_quality import MIN_SHARPNESS

DATA = load_dataset()
CASES = DATA["cases"]


def test_composicao_familias_e_demonstracao():
    assert len(CASES) == len({c["id"] for c in CASES}) == 40
    assert len({c["path"] for c in CASES}) == 40
    assert Counter(c["expected_quality"] for c in CASES) == {
        "legible": 25,
        "partial": 8,
        "illegible": 7,
    }
    assert Counter(c["split"] for c in CASES) == {"calibration": 20, "validation": 20}
    assert Counter(c["expected_quality"] for c in CASES if c["demo"]) == {
        "legible": 2,
        "illegible": 2,
    }
    assert sum(c["early_sample"] for c in CASES) == 5
    for family in {c["family_id"] for c in CASES}:
        variants = [c for c in CASES if c["family_id"] == family]
        assert len(variants) == 2
        assert len({c["split"] for c in variants}) == 1
    assert {c["degradation"]["type"] for c in CASES} == {
        "none",
        "blur",
        "low_light",
        "rotation",
        "perspective",
        "crop",
        "jpeg",
        "reflection",
    }
    for split in ("calibration", "validation"):
        assert len({c["kind"] for c in CASES if c["split"] == split}) == 3
        assert len({c["bank"] for c in CASES if c["split"] == split}) == 4


def test_gerador_reproduz_bytes_e_semente_muda_documentos():
    data, files = build()
    assert data == DATA
    for path, content in files.items():
        assert (ROOT / path).read_bytes() == content, path
    assert manifest(files) == json.loads(
        (ROOT / "research/rag_benchmark/documents_manifest.json").read_text()
    )
    other, _ = build(seed=91)
    assert other["cases"][0]["expected_fields"] != data["cases"][0]["expected_fields"]


def test_dados_pessoais_sao_constantes_invalidas_e_nomes_de_exemplo():
    assert DATA["synthetic_only"] is True
    assert DATA["personal_data"] == PERSONAL
    # CPF repetido é inválido, independentemente dos dígitos verificadores.
    assert len(set(PERSONAL["cpf"].replace(".", "").replace("-", ""))) == 1
    assert PERSONAL["account"] == "0000000-0" and PERSONAL["branch"] == "0000"
    for case in CASES:
        name = case["expected_fields"].get("counterparty")
        assert name is None or name in NAMES
        assert not {"cpf", "account", "branch"} & case["expected_fields"].keys()
        for row in case["expected_transactions"]:
            assert any(word in row["description"] for word in ("Exemplo", "Fictícia", "Sintético"))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_gabarito_corresponde_ao_contrato_e_a_visibilidade(case):
    for key, value in case["expected_fields"].items():
        ExtractedField(key=key, value=value, confidence=1.0, source=FieldSource.OCR)
    for row in case["expected_transactions"]:
        ExtractedTransaction.model_validate_json(
            json.dumps({**row, "amount": float(row["amount"]), "confidence": 1.0})
        )
    original = case["expected_fields"]
    visible = case["recoverable_fields"]
    assert all(original[key] == value for key, value in visible.items())
    if case["expected_quality"] == "legible":
        assert original == visible
    elif case["expected_quality"] == "partial":
        assert len(original) == len(visible) + 1
    else:
        assert visible == {} and case["recoverable_transactions"] == []
    if case["media_type"] == "application/pdf":
        pdf = PdfReader(io.BytesIO((ROOT / case["path"]).read_bytes()))
        assert len(pdf.pages) == 1
        assert pdf.pages[0].extract_text() == ""
        assert len(pdf.pages[0].images) == 1


@pytest.mark.parametrize(
    "case", [c for c in CASES if c["expected_quality"] == "illegible"], ids=lambda c: c["id"]
)
async def test_ilegivel_abstem_sem_chamar_ocr(case):
    assert image_metrics(case)["sharpness"] < MIN_SHARPNESS
    ocr = AsyncMock()
    ctx = DocumentContext(content=(ROOT / case["path"]).read_bytes(), media_type=case["media_type"])
    step = await DocumentAgent(ocr=ocr).run(ctx)
    assert step.status.value == "abstained"
    assert ctx.result.quality.quality == DocumentQuality.ILLEGIBLE
    assert ctx.result.abstained and ctx.result.needs_review
    assert ctx.result.fields == ctx.result.transactions == []
    ocr.read.assert_not_called()


def test_selecao_usa_so_calibracao_e_verifica_grupo_separado():
    calibration = [c for c in CASES if c["split"] == "calibration"]
    metrics = {c["id"]: image_metrics(c) for c in calibration}
    result = calibrate(calibration, metrics)
    assert result["calibration_errors"] == [0, 0]
    assert result["limits"] == {"min_side": 320, "sharpness": 15.0, "contrast": 12.0}
    with pytest.raises(ValueError, match="validação"):
        calibrate(CASES, metrics)


def test_schema_rejeita_dados_incoerentes():
    validator = Draft202012Validator(
        json.loads(SCHEMA.read_text()), format_checker=Draft202012Validator.FORMAT_CHECKER
    )
    for mutate in (
        lambda d: d.update(synthetic_only=False),
        lambda d: d["cases"][0].update(kind="unknown"),
        lambda d: d["cases"][0]["expected_fields"].update(date="2026-02-31"),
        lambda d: d["cases"][0]["expected_fields"].update(amount="1,00"),
        lambda d: d["cases"][0]["expected_fields"].pop("amount"),
        lambda d: d["cases"][-1]["recoverable_fields"].update(amount="1.00"),
        lambda d: d["cases"].pop(),
    ):
        bad = copy.deepcopy(DATA)
        mutate(bad)
        with pytest.raises(ValidationError):
            validator.validate(bad)


def test_avaliador_penaliza_omissao_campo_oculto_e_lancamento_errado():
    case = next(
        c for c in CASES if c["kind"] == "card_invoice" and c["expected_quality"] == "partial"
    )
    row = {
        "id": case["id"],
        "gate_rejected": False,
        "document": {
            "fields": [{"key": "total", "value": case["expected_fields"]["total"]}],
            "transactions": [{**case["expected_transactions"][0], "amount": 999999}],
            "abstained": False,
        },
    }
    result = summarize([case], [row])[case["split"]]
    assert result["correct_fields"] == 0
    assert result["recoverable_fields"] == len(case["recoverable_fields"])
    assert result["unexpected_fields"] == 1
    assert result["correct_transactions"] == 0 and result["unmatched_transactions"] == 1


def test_avaliador_separa_transcricao_de_erro_financeiro_sem_reutilizar_linha():
    from rag_benchmark.document_evaluation import matched_rows

    expected = [
        {
            "date": "2026-10-01",
            "amount": "1234.50",
            "description": "Papelaria Fictícia",
            "installment": None,
        }
    ]
    actual = [{**expected[0], "amount": 1234.5, "description": "PapelariaFicticia"}]
    assert matched_rows(expected, actual) == 0
    assert matched_rows(expected, actual, numeric_only=True) == 1
    assert matched_rows(expected, actual * 2, numeric_only=True) == 1
    actual[0]["amount"] = 12345.0
    assert matched_rows(expected, actual, numeric_only=True) == 0


def test_avaliador_rejeita_leituras_duplicadas_ou_incompletas():
    case = CASES[0]
    row = {"id": case["id"], "gate_rejected": False}
    with pytest.raises(ValueError, match="duplicados"):
        summarize([case], [row, row])
    with pytest.raises(ValueError, match="exatamente"):
        summarize([case], [])
