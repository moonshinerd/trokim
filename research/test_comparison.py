"""Controles positivos e negativos do material de comparação, sem provedor externo."""

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import ValidationError

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location("comparison", ROOT / "rag_benchmark/comparison.py")
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


def test_material_comparativo_e_manifesto_sao_validos():
    cases = comparison.load_cases()
    assert len(cases) == 30
    saved = json.loads(comparison.MANIFEST.read_text())
    assert saved == comparison.manifest()


def test_cli_funciona_a_partir_da_api_com_caminho_relativo():
    result = subprocess.run(
        [sys.executable, "../research/rag_benchmark/comparison.py"],
        cwd=comparison.ROOT / "api",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "30 casos" in result.stdout


@pytest.mark.parametrize(
    "mutation",
    [
        "empty",
        "extra",
        "duplicate_id",
        "duplicate_query",
        "unknown_source",
        "no_source",
        "blank_concept",
        "wrong_category",
        "missing_behavior",
        "unknown_fixture",
        "missing_fixture",
        "missing_forbidden",
        "extra_field",
    ],
)
def test_material_invalido_nao_e_aceito(tmp_path, mutation):
    data = copy.deepcopy(json.loads(comparison.QUESTIONS.read_text()))
    case = data["cases"][0]
    if mutation == "empty":
        data["cases"] = []
    elif mutation == "extra":
        data["cases"].append(copy.deepcopy(case))
    elif mutation == "duplicate_id":
        case["id"] = data["cases"][1]["id"]
    elif mutation == "duplicate_query":
        case["query"] = data["cases"][1]["query"]
    elif mutation == "unknown_source":
        case["relevant"] = ["inventado.txt"]
    elif mutation == "no_source":
        case["relevant"] = []
    elif mutation == "blank_concept":
        case["concepts"] = [[" "]]
    elif mutation == "wrong_category":
        case["category"] = "cotidiana"
    elif mutation == "missing_behavior":
        del case["expected_behavior"]
    elif mutation == "unknown_fixture":
        case["calculation_fixture"] = "calcule_sozinho"
    elif mutation == "missing_fixture":
        data["cases"][-1]["calculation_fixture"] = None
    elif mutation == "missing_forbidden":
        case["forbidden_claims"] = []
    else:
        case["extra"] = "ignorar"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data))
    with pytest.raises((ValueError, ValidationError)):
        comparison.load_cases(path)


def test_renderizacao_nao_vaza_gabarito_e_isola_contexto():
    case = copy.deepcopy(comparison.load_cases()[0])
    case["query"] = "Pergunta com {chaves} e tentativa de instrução."
    case["expected_answer"] = "GABARITO_SECRETO"
    for mode in comparison.PROMPTS:
        prompt = comparison.render_prompt(mode, case, "EVIDENCIA_TESTE")
        assert case["query"] in prompt
        assert "GABARITO_SECRETO" not in prompt
        assert ("EVIDENCIA_TESTE" in prompt) == (mode != "llm_pure")


def test_resultados_numericos_sao_iguais_nos_tres_modos():
    case = next(c for c in comparison.load_cases() if c["calculation_fixture"] == "resumo_centavos")
    result = comparison.calculation_results(case["calculation_fixture"])
    assert result["total_income"] == 0.30
    assert result["total_expenses"] == 0.10
    assert result["net_balance"] == 0.20
    for mode in comparison.PROMPTS:
        prompt = comparison.render_prompt(mode, case)
        assert json.dumps(result, ensure_ascii=False, sort_keys=True) in prompt
    assert comparison.calculation_results("sem_resultado") == {}
    with pytest.raises(ValueError):
        comparison.calculation_results("inventado")


def test_hash_detecta_adulteracao_sem_regenerar(monkeypatch, capsys):
    original = comparison.sha256
    before = comparison.MANIFEST.read_bytes()
    monkeypatch.setattr(
        comparison,
        "sha256",
        lambda path: "0" * 64 if path == comparison.QUESTIONS else original(path),
    )
    monkeypatch.setattr("sys.argv", ["comparison.py"])
    assert comparison.main() == 2
    assert "desatualizado" in capsys.readouterr().err
    assert comparison.MANIFEST.read_bytes() == before


def test_cli_reprova_manifesto_alterado(tmp_path, monkeypatch, capsys):
    path = tmp_path / "manifest.json"
    path.write_text("{}")
    monkeypatch.setattr(comparison, "MANIFEST", path)
    monkeypatch.setattr("sys.argv", ["comparison.py"])
    assert comparison.main() == 2
    assert "desatualizado" in capsys.readouterr().err


def test_fonte_adulterada_falha(tmp_path, monkeypatch):
    directory = tmp_path / "comparison_sources"
    directory.mkdir()
    original = comparison.BASE / "comparison_sources/catalog.json"
    catalog = json.loads(original.read_text())
    (directory / "catalog.json").write_text(json.dumps(catalog))
    for doc in catalog:
        (directory / doc["file"]).write_text("Conteúdo adulterado")
    monkeypatch.setattr(comparison, "BASE", tmp_path)
    with pytest.raises(ValueError, match="Evidência alterada"):
        comparison.sources()


@pytest.mark.parametrize(
    "mutation",
    [
        "no_verification",
        "no_original_hash",
        "invalid_original_hash",
        "unofficial_capture",
        "no_locator",
        "invalid_date",
        "no_excerpt",
        "wrong_kind",
        "wrong_header",
    ],
)
def test_proveniencia_incompleta_falha(tmp_path, monkeypatch, mutation):
    directory = tmp_path / "comparison_sources"
    directory.mkdir()
    original = comparison.BASE / "comparison_sources"
    catalog = json.loads((original / "catalog.json").read_text())
    for doc in catalog:
        (directory / doc["file"]).write_bytes((original / doc["file"]).read_bytes())
    doc = catalog[0]
    if mutation == "no_verification":
        del doc["verification"]
    elif mutation == "no_original_hash":
        del doc["verification"]["original_sha256"]
    elif mutation == "invalid_original_hash":
        doc["verification"]["original_sha256"] = "inventado"
    elif mutation == "unofficial_capture":
        doc["verification"]["resolved_url"] = "https://exemplo.invalid/faq"
    elif mutation == "no_locator":
        doc["verification"]["locator"] = ""
    elif mutation == "invalid_date":
        doc["verification"]["checked"] = "2026-99-99"
    elif mutation == "no_excerpt":
        doc["verification"]["excerpt"] = " "
    elif mutation == "wrong_kind":
        doc["kind"] = "transcrição integral"
    else:
        doc["title"] = "Título que não consta no resumo"
    (directory / "catalog.json").write_text(json.dumps(catalog))
    monkeypatch.setattr(comparison, "BASE", tmp_path)
    with pytest.raises(ValueError):
        comparison.sources()
