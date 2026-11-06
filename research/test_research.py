"""Validação independente da curadoria, do gabarito e da massa sintética."""

import hashlib
import importlib.util
import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from ofxparse import OfxParser
from pypdf import PdfReader

from app.services.parser_service import ParserService
from app.services.rag_service import RAGService

ROOT = Path(__file__).parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


benchmark = load_module("benchmark", ROOT / "rag_benchmark/eval_rag.py")
generator = load_module("generator", ROOT / "synthetic_data/generate_datasets.py")


def test_catalogo_rastreavel():
    directory = ROOT / "knowledge_base"
    catalog = json.loads((directory / "catalog.json").read_text())
    assert len(catalog) >= 20
    assert len({urlsplit(d["url"]).path.rstrip("/") for d in catalog}) >= 20
    assert len({d["id"] for d in catalog}) == len(catalog)
    assert {d["file"] for d in catalog} == {p.name for p in directory.glob("*.txt")}
    for doc in catalog:
        path = directory / doc["file"]
        content = path.read_text()
        assert f"FONTE: {doc['source']}" in content
        assert f"TITULO: {doc['title']}" in content
        assert f"URL: {doc['url']}" in content
        assert "[SEÇÃO 1:" in content and content.count("[SEÇÃO") == 1
        assert urlsplit(doc["url"]).hostname in {
            "www.bcb.gov.br",
            "aprendervalor.bcb.gov.br",
            "www.gov.br",
            "www.consumerfinance.gov",
            "files.consumerfinance.gov",
        }
        assert doc["kind"] == "resumo editorial"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == doc["chunk_sha256"]
        assert date.fromisoformat(doc["accessed"])
        verification = doc["verification"]
        assert verification["excerpt"] and verification["locator"]
        assert len(verification["excerpt"].split()) <= 25
        if "original_sha256" in verification:
            assert re.fullmatch(r"[a-f0-9]{64}", verification["original_sha256"])
        else:
            assert doc["id"] == "bcb_calculadora"
            assert "índice de busca" in verification["method"]
    assert len(RAGService().chunks) == len(catalog)
    assert all(chunk.source_url for chunk in RAGService().chunks)


def test_massa_sintetica_e_reproducivel(tmp_path):
    directory = ROOT / "synthetic_data"
    generator.generate_synthetic_samples(str(tmp_path))
    first_pdf = (tmp_path / "fatura_sintetica_novembro.pdf").read_bytes()
    generator.generate_synthetic_samples(str(tmp_path))
    assert (tmp_path / "fatura_sintetica_novembro.pdf").read_bytes() == first_pdf
    ofx_path = directory / "extrato_sintetico_novembro.ofx"
    assert ofx_path.read_bytes() == (tmp_path / ofx_path.name).read_bytes()
    with ofx_path.open("rb") as stream:
        statement = OfxParser.parse(stream).account.statement
    assert sum(t.amount for t in statement.transactions) == statement.balance == Decimal("2849.50")
    transactions = ParserService.parse_ofx(ofx_path.read_bytes())
    assert [t.amount for t in transactions] == [5000, 650.50, 1500]
    assert len({t.id for t in transactions}) == 3
    assert all(t.account_id == "TESTE-SINTETICO-0001" for t in transactions)
    assert [t.type.value for t in transactions] == ["credit", "debit", "debit"]
    pdf = directory / "fatura_sintetica_novembro.pdf"
    text = "\n".join(p.extract_text() for p in PdfReader(pdf).pages)
    assert text == "\n".join(p.extract_text() for p in PdfReader(tmp_path / pdf.name).pages)
    assert "SINTÉTICA" in text and "Sem titular, CPF ou cartão reais" in text
    purchases = ParserService.parse_pdf_text(text)
    assert [t.amount for t in purchases] == [650.50, 120, 45]
    assert sum(Decimal(str(t.amount)) for t in purchases) == Decimal("815.50")
    assert all(t.type.value == "debit" for t in purchases)
    assert all(t.date.year == 2026 and t.date.month == 11 for t in transactions + purchases)


def test_benchmark_atinge_metas_e_gabarito_cobre_catalogo():
    report = benchmark.evaluate()
    assert report["passed"], [c["id"] for c in report["cases"] if not c["passed"]]
    assert report["counts"] == {"in_domain": 41, "abstention": 20}
    expected = {c.id for c in RAGService().chunks}
    assert {ev for c in report["cases"] for ev in c["relevant"]} == expected


def test_benchmark_reprova_abstencao_total_e_resposta_inventada():
    class Empty:
        def answer_query(self, query):
            return {"answered": False, "evidences": [], "answer": "Sem dados."}

    class Invented:
        def answer_query(self, query):
            result = RAGService().answer_query(query)
            result["answer"] = "Invista tudo: retorno garantido de 100% ao mês."
            return result

    empty = benchmark.evaluate(Empty())
    assert not empty["passed"] and empty["metrics"]["recall_at_3"] == 0

    class ExtraAdvice:
        def answer_query(self, query):
            result = RAGService().answer_query(query)
            if result["answered"]:
                result["answer"] += "\nCompre qualquer ação sem risco."
            return result

    extra = benchmark.evaluate(ExtraAdvice())
    assert not extra["passed"] and extra["metrics"]["grounded_accuracy"] == 0
    invented = benchmark.evaluate(Invented())
    assert not invented["passed"]
    assert invented["metrics"]["grounded_accuracy"] == 0


@pytest.mark.parametrize(
    "mutation",
    [
        "empty",
        "no_adversarial",
        "no_domain",
        "duplicate",
        "unknown",
        "no_concepts",
        "empty_alternative",
    ],
)
def test_gabarito_invalido_falha_explicitamente(tmp_path, mutation):
    cases = benchmark.load_cases()
    if mutation == "empty":
        cases = []
    elif mutation == "no_adversarial":
        cases = [c for c in cases if c["relevant"]]
    elif mutation == "no_domain":
        cases = [c for c in cases if not c["relevant"]]
    elif mutation == "duplicate":
        cases.append(cases[0])
    elif mutation == "unknown":
        cases[0]["relevant"] = ["inventado.txt_1"]
    elif mutation == "no_concepts":
        cases[0]["concepts"] = []
    else:
        cases[0]["concepts"] = [[""]]
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases))
    with pytest.raises(ValueError):
        benchmark.load_cases(path)


def test_snapshots_correspondem_ao_codigo_e_ao_gabarito():
    current = benchmark.evaluate()
    for filename in ("current.json", "baseline.json"):
        saved = json.loads((ROOT / "rag_benchmark/results" / filename).read_text())
        for key in ("questions_sha256", "corpus_sha256", "service_sha256", "evaluator_sha256"):
            assert saved["provenance"][key] == current["provenance"][key]
    saved_current = json.loads((ROOT / "rag_benchmark/results/current.json").read_text())
    assert saved_current["metrics"] == pytest.approx(current["metrics"])
