"""Avaliação reproduzível de recuperação, resposta extrativa e abstenção."""

import argparse
import hashlib
import json
import platform
import sys
import unicodedata
from importlib.metadata import version
from pathlib import Path
from typing import Protocol

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))
from app.core.config import settings  # noqa: E402
from app.services.rag_service import RAGService  # noqa: E402

QUESTIONS = Path(__file__).with_name("questions.json")
BASE = ROOT / "research/knowledge_base"


class Answerer(Protocol):
    def answer_query(self, query: str) -> dict: ...


class RetrievalOnlyRAG(RAGService):
    """Controle de ablação: mesmo índice, sem política explícita de escopo."""

    @staticmethod
    def _outside_scope(query: str) -> bool:
        return False


def normalized(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def fingerprint(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def load_cases(path: Path = QUESTIONS) -> list[dict]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    ids = set()
    valid_ids = {p.name for p in BASE.glob("*.txt")}
    if not isinstance(cases, list) or not cases:
        raise ValueError("Gabarito deve ser uma lista não vazia.")
    for case in cases:
        if not isinstance(case, dict) or set(case) != {
            "id",
            "query",
            "relevant",
            "expected_answer",
            "concepts",
            "category",
        }:
            raise ValueError(
                "Caso deve conter ID, pergunta, evidências, resposta, conceitos e categoria."
            )
        if not isinstance(case["id"], str) or not case["id"] or case["id"] in ids:
            raise ValueError("IDs de casos devem ser únicos e não vazios.")
        ids.add(case["id"])
        if not all(
            isinstance(case[k], str) and case[k].strip()
            for k in ("query", "expected_answer", "category")
        ):
            raise ValueError("Pergunta, categoria e resposta esperada são obrigatórias.")
        relevant = case["relevant"]
        if not isinstance(relevant, list) or not all(isinstance(x, str) for x in relevant):
            raise ValueError("Evidências devem ser uma lista de IDs.")
        if len(set(relevant)) != len(relevant) or not set(relevant) <= valid_ids:
            raise ValueError("Gabarito referencia evidência duplicada ou inexistente.")
        concepts = case["concepts"]
        if not isinstance(concepts, list) or any(
            not isinstance(group, list)
            or not group
            or any(not isinstance(term, str) or not term.strip() for term in group)
            for group in concepts
        ):
            raise ValueError("Conceitos devem conter grupos não vazios de alternativas textuais.")
        if bool(relevant) != bool(concepts):
            raise ValueError(
                "Perguntas no domínio precisam de conceitos; abstenções não os admitem."
            )
    if not any(c["relevant"] for c in cases) or not any(not c["relevant"] for c in cases):
        raise ValueError("Gabarito deve conter perguntas no domínio e de abstenção.")
    return cases


def evaluate(rag: Answerer | None = None, cases_path: Path = QUESTIONS) -> dict:
    rag = rag if rag is not None else RAGService(top_k=3)
    cases = load_cases(cases_path)
    corpus = {c.id: c for c in RAGService().chunks}
    details = []
    for case in cases:
        result = rag.answer_query(case["query"])
        evidences = result["evidences"]
        # Mantém ordem: apenas a primeira evidência é usada na resposta extrativa atual.
        retrieved = [ev["document_id"] for ev in evidences[:3]]
        relevant = set(case["relevant"])
        recall = len(relevant & set(retrieved)) / len(relevant) if relevant else None
        answer = result.get("answer", "")
        concepts_ok = all(
            any(normalized(term) in normalized(answer) for term in group)
            for group in case["concepts"]
        )
        primary = corpus.get(evidences[0]["id"]) if evidences else None
        expected_extraction = (
            (
                f"Com base nas diretrizes do {primary.source_name} ({primary.section}):\n\n"
                f"{primary.content}\n\nFonte oficial citada: {primary.document_title}."
                f"\nURL: {primary.source_url}"
            )
            if primary
            else None
        )
        # Contrato deste protótipo: somente extração + citação; conselhos extras reprovam.
        grounded = bool(
            result["answered"]
            and primary
            and primary.document_id in relevant
            and answer == expected_extraction
            and primary.source_url
            and concepts_ok
        )
        abstained = (
            not result["answered"]
            and not evidences
            and result.get("status") == "abstained"
            and "não possui evidências suficientes" in answer
        )
        passed = grounded if relevant else abstained
        details.append(
            {
                **case,
                "retrieved": retrieved,
                "recall_at_3": recall,
                "concepts_ok": concepts_ok if relevant else None,
                "answered": result["answered"],
                "answer": answer,
                "passed": passed,
            }
        )
    valid = [d for d in details if d["relevant"]]
    outside = [d for d in details if not d["relevant"]]
    metrics = {
        "recall_at_3": sum(d["recall_at_3"] for d in valid) / len(valid),
        "grounded_accuracy": sum(d["passed"] for d in valid) / len(valid),
        "abstention_accuracy": sum(d["passed"] for d in outside) / len(outside),
    }
    return {
        "schema_version": 3,
        "configuration": {
            "top_k": 3,
            "threshold": getattr(rag, "threshold", settings.RAG_SIMILARITY_THRESHOLD),
            "representation": "híbrida: cosseno denso + tfidf(words=1:2,chars=3:5;weights=.5/.5)",
            "embedding_model": settings.RAG_EMBEDDING_MODEL,
            "hybrid_alpha": getattr(rag, "alpha", settings.RAG_HYBRID_ALPHA),
            "vector_store": "sqlite-vec (vec0)",
            "chunk_max_chars": settings.RAG_CHUNK_MAX_CHARS,
            "chunk_overlap_tokens": settings.RAG_CHUNK_OVERLAP_TOKENS,
        },
        "provenance": {
            "questions_sha256": fingerprint([cases_path]),
            "evaluator_sha256": fingerprint([Path(__file__)]),
            "corpus_sha256": fingerprint(list(BASE.glob("*.txt")) + [BASE / "catalog.json"]),
            "service_sha256": fingerprint(
                [
                    ROOT / "api/app/services" / name
                    for name in ("rag_service.py", "chunking_service.py", "ingestion_service.py")
                ]
                + list((ROOT / "api/app/clients").glob("*.py"))
                + [ROOT / "api/app/core/config.py"]
            ),
            "python": platform.python_version(),
            "scikit_learn": version("scikit-learn"),
            "fastembed": version("fastembed"),
            "sqlite_vec": version("sqlite-vec"),
            "embedding_model": settings.RAG_EMBEDDING_MODEL,
            "hybrid_alpha": getattr(rag, "alpha", settings.RAG_HYBRID_ALPHA),
            "vector_store": "sqlite-vec (vec0)",
            "chunk_max_chars": settings.RAG_CHUNK_MAX_CHARS,
            "chunk_overlap_tokens": settings.RAG_CHUNK_OVERLAP_TOKENS,
            "policy": type(rag).__name__,
        },
        "counts": {"in_domain": len(valid), "abstention": len(outside)},
        "metrics": metrics,
        "passed": (
            metrics["recall_at_3"] >= 0.9
            and metrics["grounded_accuracy"] >= 0.9
            and metrics["abstention_accuracy"] == 1
        ),
        "cases": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cases", type=Path, default=QUESTIONS)
    parser.add_argument(
        "--retrieval-only", action="store_true", help="Executar controle sem política"
    )
    args = parser.parse_args()
    try:
        rag = RetrievalOnlyRAG(top_k=3) if args.retrieval_only else None
        report = evaluate(rag, args.cases)
    except (ValueError, KeyError, OSError) as exc:
        print(f"Erro na avaliação: {exc}", file=sys.stderr)
        return 2
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(
        json.dumps({k: v for k, v in report.items() if k != "cases"}, ensure_ascii=False, indent=2)
    )
    for case in report["cases"]:
        if not case["passed"]:
            print(f"FALHA {case['id']}: {case['query']} -> {case['retrieved']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
