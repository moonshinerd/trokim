"""Valida o material comparativo da #20; não executa modelos nem pontua respostas."""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from string import Formatter
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "research/synthetic_data"))
from generate_comparison_data import calculation_results  # noqa: E402

BASE = Path(__file__).resolve().parent
QUESTIONS = BASE / "questions_comparison.json"
SCHEMA = BASE / "questions_comparison.schema.json"
MANIFEST = BASE / "comparison_manifest.json"
PROMPTS = {
    "llm_pure": ROOT / "api/app/prompts/prompt_llm_pure_v1.txt",
    "naive_rag": ROOT / "api/app/prompts/prompt_naive_rag_v1.txt",
    "trokim_grounded": ROOT / "api/app/prompts/prompt_trokim_grounded_v1.txt",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources() -> dict[str, tuple[dict, Path]]:
    """Une os catálogos sem alterar a base usada pelo benchmark da semana 2."""
    result = {}
    for directory in (ROOT / "research/knowledge_base", BASE / "comparison_sources"):
        for doc in json.loads((directory / "catalog.json").read_text(encoding="utf-8")):
            name = doc["file"]
            if Path(name).name != name or name in result or not name.endswith(".txt"):
                raise ValueError("Arquivo de evidência inválido ou duplicado.")
            path = directory / name
            if sha256(path) != doc["chunk_sha256"]:
                raise ValueError(f"Evidência alterada: {name}")
            official_hosts = {
                "www.bcb.gov.br",
                "normativos.bcb.gov.br",
                "aprendervalor.bcb.gov.br",
                "www.gov.br",
                "www.consumerfinance.gov",
                "files.consumerfinance.gov",
            }
            if (
                urlsplit(doc["url"]).hostname not in official_hosts
                or urlsplit(doc["url"]).scheme != "https"
            ):
                raise ValueError(f"Fonte não oficial: {name}")
            date.fromisoformat(doc["accessed"])
            if not doc["locator"].strip():
                raise ValueError("Fonte sem localização verificável.")
            if doc["id"] != path.stem or doc["kind"] != "resumo editorial":
                raise ValueError("Identidade ou tipo editorial da fonte inválido.")
            content = path.read_text(encoding="utf-8")
            headers = (
                f"FONTE: {doc['source']}",
                f"TITULO: {doc['title']}",
                f"URL: {doc['url']}",
                f"CONSULTA: {doc['accessed']}",
            )
            if any(header not in content.splitlines() for header in headers):
                raise ValueError("Cabeçalhos da evidência divergem do catálogo.")
            if content.count("[SEÇÃO") != 1 or "[SEÇÃO 1:" not in content:
                raise ValueError("Resumo deve conter uma seção identificável.")
            verification = doc.get("verification", {})
            for key in ("method", "checked", "locator", "excerpt"):
                if not isinstance(verification.get(key), str) or not verification[key].strip():
                    raise ValueError(f"Conferência oficial incompleta: {name}/{key}")
            date.fromisoformat(verification["checked"])
            if len(verification["excerpt"].split()) > 25:
                raise ValueError("Excerto de conferência deve ter no máximo 25 palavras.")
            original_hash = verification.get("original_sha256")
            if original_hash is None:
                if name != "bcb_calculadora.txt" or "índice de busca" not in verification["method"]:
                    raise ValueError("Falta hash dos bytes oficiais conferidos.")
            elif not isinstance(original_hash, str) or not re.fullmatch(
                r"[a-f0-9]{64}", original_hash
            ):
                raise ValueError("Hash do conteúdo oficial inválido.")
            if original_hash is not None:
                resolved = urlsplit(verification.get("resolved_url", ""))
                if resolved.scheme != "https" or resolved.hostname not in official_hosts:
                    raise ValueError("URL de conferência não oficial.")
            result[name] = (doc, path)
    return result


def load_cases(path: Path = QUESTIONS) -> list[dict]:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    data = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(data)
    cases = data["cases"]
    if len({case["id"] for case in cases}) != 30:
        raise ValueError("São necessários 30 IDs únicos.")
    if Counter(case["category"] for case in cases) != {
        "conceitual": 10,
        "cotidiana": 10,
        "armadilha": 10,
    }:
        raise ValueError("São necessários dez casos por categoria.")
    if len({case["query"].strip().casefold() for case in cases}) != 30:
        raise ValueError("Perguntas repetidas.")
    catalog = sources()
    for case in cases:
        relevant = case["relevant"]
        if not set(relevant) <= catalog.keys():
            raise ValueError(f"Evidência inexistente: {case['id']}")
        if case["expected_behavior"] != "abster" and not relevant:
            raise ValueError("Responder ou corrigir exige evidência.")
        if any(name.startswith("anpd_") for name in relevant):
            raise ValueError("ANPD não fundamenta orientação financeira neste conjunto.")
        calculation_results(case["calculation_fixture"])
    behaviors = {case["expected_behavior"] for case in cases}
    if behaviors != {"responder", "corrigir_premissa", "abster"}:
        raise ValueError("Faltam casos de resposta, correção ou abstenção.")
    if {case["calculation_fixture"] for case in cases} != {
        None,
        "resumo_centavos",
        "sem_resultado",
    }:
        raise ValueError("Faltam controles de cálculo fornecido/ausente.")
    for mode, prompt in PROMPTS.items():
        fields = [
            field for _, field, _, _ in Formatter().parse(prompt.read_text()) if field is not None
        ]
        expected = {"question", "calculation_results"}
        if mode != "llm_pure":
            expected.add("context")
        if set(fields) != expected or len(fields) != len(expected):
            raise ValueError(f"Variáveis de prompt inválidas: {mode}")
    return cases


def render_prompt(mode: str, case: dict, context: str = "") -> str:
    """Não injeta gabarito. #24 deve fornecer os mesmos trechos aos dois modos RAG."""
    values = calculation_results(case["calculation_fixture"])
    return (
        PROMPTS[mode]
        .read_text(encoding="utf-8")
        .format(
            question=case["query"],
            context=context,
            calculation_results=json.dumps(values, ensure_ascii=False, sort_keys=True),
        )
    )


def manifest() -> dict:
    paths = [
        QUESTIONS,
        SCHEMA,
        Path(__file__).resolve(),
        *PROMPTS.values(),
        ROOT / "research/synthetic_data/generate_comparison_data.py",
        ROOT / "api/app/services/calculation_service.py",
        ROOT / "api/app/domain/models.py",
        ROOT / "research/knowledge_base/catalog.json",
        BASE / "comparison_sources/catalog.json",
    ]
    paths.extend(path for _, path in sources().values())
    return {
        "schema_version": 1,
        "hash_algorithm": "sha256-bytes",
        "files": {str(path.relative_to(ROOT)): sha256(path) for path in sorted(paths)},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-manifest",
        action="store_true",
        help="Atualizar hashes após revisão explícita dos materiais",
    )
    args = parser.parse_args()
    try:
        cases = load_cases()
        current = manifest()
        if args.write_manifest:
            MANIFEST.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n")
        elif json.loads(MANIFEST.read_text(encoding="utf-8")) != current:
            raise ValueError("Manifesto desatualizado: revisar alterações antes de regenerar.")
        print(f"Material válido: {len(cases)} casos, 3 prompts, fontes e hashes conferidos.")
        return 0
    except (ValueError, OSError, KeyError, ValidationError) as exc:
        print(f"Erro no material comparativo: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
