"""Benchmark automatizado comparativo: LLM Pura vs. Naive RAG vs. Trokim Estruturado.

Executa as 30 perguntas do gabarito da Semana 3 (Issue #20 e #24) sobre as 3 abordagens,
mede latência e métricas de alucinação/fidelidade/abstenção (Issue #21) e grava os
artefatos auditados em artifacts/research/.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.pipeline import FeatureUnion

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent

sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(BASE))

from comparison import load_cases, render_prompt, sources  # noqa: E402
from eval_comparison import evaluate_comparison, render_markdown  # noqa: E402

from app.clients.fastembed_embeddings import get_default_embedder  # noqa: E402
from app.clients.llm_factory import get_llm_provider  # noqa: E402
from app.clients.sqlite_vector_store import SQLiteVectorStore  # noqa: E402
from app.domain.models import EvidenceChunk  # noqa: E402
from app.models.llm_provider import LLMProvider  # noqa: E402
from app.services.generation_service import ABSTENTION_MESSAGE  # noqa: E402
from app.services.ingestion_service import parse_document  # noqa: E402
from app.services.rag_service import RAGService  # noqa: E402

DEFAULT_CASES = BASE / "questions_comparison.json"
DEFAULT_RESULTS = ROOT / "artifacts/research/comparison_results.json"
DEFAULT_REPORT_JSON = ROOT / "artifacts/research/comparison_report.json"
DEFAULT_REPORT_MD = ROOT / "artifacts/research/comparison_report.md"
DEFAULT_CHART_SVG = ROOT / "artifacts/research/comparison_metrics.svg"
DEFAULT_VECTOR_DB = ROOT / "artifacts/research/comparison_vectors.db"


class UnifiedCorpusRetriever:
    """Índice unificado para o experimento comparativo da Semana 3.

    Indexa as 20 fontes de research/knowledge_base mais as 2 fontes suplementares
    de comparison_sources (totalizando 22 documentos oficiais).
    """

    def __init__(self, db_path: Path = DEFAULT_VECTOR_DB) -> None:
        self.db_path = db_path
        self.embedder = get_default_embedder()
        self.store = SQLiteVectorStore(self.db_path, dimension=self.embedder.dimension)
        self.chunks: list[EvidenceChunk] = []
        self.vectorizer: FeatureUnion | None = None
        self.tfidf_matrix = None
        self._build_index()

    def _build_index(self) -> None:
        catalog = sources()
        all_chunks: list[EvidenceChunk] = []
        for name, (_, path) in sorted(catalog.items()):
            text = path.read_text(encoding="utf-8")
            all_chunks.extend(parse_document(text, name))

        self.chunks = all_chunks

        # Ingestão densa idempotente
        if self.store.count() != len(self.chunks):
            self.store.reset()
            vectors = self.embedder.embed_documents(
                [f"{c.document_title}. {c.section}. {c.content}" for c in self.chunks]
            )
            self.store.add(self.chunks, vectors)

        # Ajuste do índice léxico (TF-IDF palavras + caracteres)
        corpus = [f"{c.document_title}. {c.section}. {c.content}" for c in self.chunks]
        self.vectorizer = FeatureUnion(
            [
                (
                    "words",
                    TfidfVectorizer(
                        lowercase=True,
                        strip_accents="unicode",
                        ngram_range=(1, 2),
                        stop_words=[
                            "a",
                            "as",
                            "o",
                            "os",
                            "de",
                            "da",
                            "das",
                            "do",
                            "dos",
                            "e",
                            "em",
                            "um",
                            "uma",
                            "para",
                            "por",
                            "com",
                            "que",
                            "qual",
                            "quais",
                            "como",
                            "no",
                            "na",
                            "nos",
                            "nas",
                            "ao",
                            "aos",
                            "se",
                            "meu",
                            "minha",
                        ],
                    ),
                ),
                (
                    "chars",
                    TfidfVectorizer(
                        analyzer="char_wb",
                        ngram_range=(3, 5),
                        strip_accents="unicode",
                    ),
                ),
            ],
            transformer_weights={"words": 0.5, "chars": 0.5},
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)

    def retrieve_dense(self, query: str, top_k: int = 3) -> list[EvidenceChunk]:
        """Recuperação vetorial puramente densa (FastEmbed 384d, alpha=1.0) para Naive RAG."""
        if not query.strip() or self.store.count() == 0:
            return []
        dense_hits = self.store.search(self.embedder.embed_query(query), self.store.count())
        results: list[EvidenceChunk] = []
        seen_documents: set[str] = set()
        for chunk, score in dense_hits:
            doc_key = chunk.document_id or chunk.id
            if doc_key in seen_documents:
                continue
            seen_documents.add(doc_key)
            item = chunk.model_copy()
            item.score = round(score, 4)
            results.append(item)
            if len(results) == top_k:
                break
        return results

    def retrieve_hybrid(
        self, query: str, top_k: int = 3, threshold: float = 0.15, alpha: float = 0.3
    ) -> list[EvidenceChunk]:
        """Recuperação híbrida calibrada (FastEmbed 384d + TF-IDF) para Trokim Estruturado."""
        if not self.vectorizer or self.tfidf_matrix is None or not self.chunks or not query.strip():
            return []

        query_vec = self.vectorizer.transform([query])
        tfidf_sims = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        dense_hits = self.store.search(self.embedder.embed_query(query), self.store.count())
        dense_sims = {chunk.id: sim for chunk, sim in dense_hits}

        scored = [
            (
                idx,
                alpha * dense_sims.get(chunk.id, 0.0) + (1.0 - alpha) * float(tfidf_sims[idx]),
            )
            for idx, chunk in enumerate(self.chunks)
        ]
        scored.sort(key=lambda item: item[1], reverse=True)

        results: list[EvidenceChunk] = []
        seen_documents: set[str] = set()
        for idx, score in scored:
            if score <= 0 or score < threshold:
                break
            chunk = self.chunks[idx]
            doc_key = chunk.document_id or chunk.id
            if doc_key in seen_documents:
                continue
            seen_documents.add(doc_key)
            item = chunk.model_copy()
            item.score = round(score, 4)
            results.append(item)
            if len(results) == top_k:
                break
        return results


def format_context(chunks: list[EvidenceChunk]) -> str:
    """Formata os trechos recuperados em blocos estruturados com órgão, título e seção."""
    if not chunks:
        return "Nenhum trecho relevante recuperado da base de dados."
    blocks = []
    for idx, chunk in enumerate(chunks, 1):
        source_line = f"[{idx}] Órgão: {chunk.source_name} | Seção: {chunk.section}"
        doc_line = f"Documento: {chunk.document_title}"
        content_line = f"Trecho: {chunk.content.strip()}"
        blocks.append(f"{source_line}\n{doc_line}\n{content_line}")
    return "\n\n".join(blocks)


async def execute_case_pure(
    case: dict[str, Any],
    llm: LLMProvider,
    temperature: float = 0.1,
    max_tokens: int = 300,
) -> dict[str, Any]:
    """Abordagem 1: LLM Pura (sem contexto documental, apenas conhecimento paramétrico)."""
    prompt = render_prompt("llm_pure", case, context="")
    t0 = time.perf_counter()
    res = await llm.generate(
        prompt=prompt,
        context_chunks=None,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    return {
        "answer": res.content.strip(),
        "status": "pure_baseline",
        "answered": True,
        "abstained": False,
        "latency_ms": latency_ms,
        "prompt_tokens": res.prompt_tokens,
        "completion_tokens": res.completion_tokens,
    }


async def execute_case_naive(
    case: dict[str, Any],
    retriever: UnifiedCorpusRetriever,
    llm: LLMProvider,
    temperature: float = 0.1,
    top_k: int = 3,
    max_tokens: int = 300,
) -> dict[str, Any]:
    """Abordagem 2: Naive RAG (recuperação densa pura, sem controle de escopo nem abstenção)."""
    query = case["query"]
    t0 = time.perf_counter()
    chunks = retriever.retrieve_dense(query, top_k=top_k)
    context_text = format_context(chunks)
    prompt = render_prompt("naive_rag", case, context=context_text)
    res = await llm.generate(
        prompt=prompt,
        context_chunks=chunks,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    return {
        "answer": res.content.strip(),
        "status": "naive_rag",
        "answered": True,
        "abstained": False,
        "latency_ms": latency_ms,
        "prompt_tokens": res.prompt_tokens,
        "completion_tokens": res.completion_tokens,
        "retrieved_chunks": [c.id for c in chunks],
    }


async def execute_case_grounded(
    case: dict[str, Any],
    retriever: UnifiedCorpusRetriever,
    llm: LLMProvider,
    temperature: float = 0.1,
    top_k: int = 3,
    threshold: float = 0.15,
    max_tokens: int = 300,
) -> dict[str, Any]:
    """Abordagem 3: Trokim Estruturado (híbrido, cálculo determinístico e abstenção ativa)."""
    query = case["query"]
    t0 = time.perf_counter()

    # 1. Filtro semântico de escopo (ADR 0002/0003)
    if RAGService._outside_scope(query):
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "answer": ABSTENTION_MESSAGE,
            "status": "abstained",
            "answered": False,
            "abstained": True,
            "latency_ms": latency_ms,
            "evidences": [],
        }

    # 2. Recuperação híbrida calibrada (alpha=0.3)
    chunks = retriever.retrieve_hybrid(query, top_k=top_k, threshold=threshold)
    if not chunks:
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "answer": ABSTENTION_MESSAGE,
            "status": "abstained",
            "answered": False,
            "abstained": True,
            "latency_ms": latency_ms,
            "evidences": [],
        }

    # 3. Síntese generativa fundamentada com citação estrita
    context_text = format_context(chunks)
    prompt = render_prompt("trokim_grounded", case, context=context_text)
    res = await llm.generate(
        prompt=prompt,
        context_chunks=chunks,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    return {
        "answer": res.content.strip(),
        "status": "grounded",
        "answered": True,
        "abstained": False,
        "latency_ms": latency_ms,
        "prompt_tokens": res.prompt_tokens,
        "completion_tokens": res.completion_tokens,
        "retrieved_chunks": [c.id for c in chunks],
    }


async def run_benchmark(
    cases: list[dict[str, Any]],
    llm: LLMProvider,
    retriever: UnifiedCorpusRetriever,
    temperature: float = 0.1,
) -> dict[str, Any]:
    """Executa as 3 abordagens sobre todos os casos de teste e mede tempos."""
    results_cases: list[dict[str, Any]] = []

    total = len(cases)
    for idx, case in enumerate(cases, 1):
        case_id = case["id"]
        category = case["category"]
        behavior = case.get("expected_behavior", "responder")
        print(f"[{idx:02d}/{total:02d}] Executando {case_id} ({category} | {behavior})...")

        # 1. LLM Pura
        pure_res = await execute_case_pure(case, llm, temperature=temperature)

        # 2. Naive RAG
        naive_res = await execute_case_naive(case, retriever, llm, temperature=temperature)

        # 3. Trokim Estruturado
        grounded_res = await execute_case_grounded(case, retriever, llm, temperature=temperature)

        results_cases.append(
            {
                "id": case_id,
                "category": category,
                "expected_behavior": behavior,
                "query": case["query"],
                "responses": {
                    "llm_pura": pure_res,
                    "rag_ingenuo": naive_res,
                    "trokim_estruturado": grounded_res,
                },
            }
        )

    # Agrega metadados e latências médias
    mean_latencies = {}
    for method in ("llm_pura", "rag_ingenuo", "trokim_estruturado"):
        lats = [c["responses"][method]["latency_ms"] for c in results_cases]
        mean_latencies[method] = round(sum(lats) / len(lats), 2) if lats else 0.0

    return {
        "schema_version": 1,
        "description": "Benchmark comparativo experimental Semana 3 (Issue #24)",
        "generated_at": datetime.now(UTC).isoformat(),
        "model_name": getattr(llm, "model", getattr(llm, "model_name", "qwen2.5")),
        "provider": getattr(llm, "name", "unknown"),
        "temperature": temperature,
        "total_cases": total,
        "mean_latency_ms": mean_latencies,
        "cases": results_cases,
    }


def generate_svg_chart(report: dict[str, Any], output_path: Path) -> None:
    """Gera gráfico SVG profissional comparando as métricas das 3 abordagens."""
    methods = [
        ("llm_pura", "LLM Pura", "#f87171"),
        ("rag_ingenuo", "Naive RAG", "#fbbf24"),
        ("trokim_estruturado", "Trokim Estruturado", "#34d399"),
    ]

    metric_keys = [
        ("factual_inconsistency_rate", "Inconsistência (Alucinação)", True),
        ("token_f1", "SQuAD F1 (Tokens)", False),
        ("concept_recall", "Concept Coverage Recall", False),
        ("abstention_f1", "Abstenção Ativa (F1)", False),
    ]

    width = 920
    height = 540
    margin_left = 60
    margin_top = 90
    margin_right = 40
    chart_width = width - margin_left - margin_right
    cluster_width = chart_width / len(metric_keys)
    bar_width = 38
    plot_height = 240

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        'width="100%" height="100%" '
        'style="background:#0f172a; font-family:system-ui,-apple-system,sans-serif;">',
        "  <!-- Header -->",
        '  <text x="50" y="45" fill="#f8fafc" font-size="20" font-weight="700">'
        "Trokim — Benchmark Comparativo Semana 3 (Issue #24)</text>",
        '  <text x="50" y="68" fill="#94a3b8" font-size="13">'
        "Avaliação empírica: Redução de Alucinações, Fidelidade e Abstenção (Qwen 2.5)</text>",
        "",
        "  <!-- Grid Lines (0% a 100%) -->",
    ]

    for p in range(0, 101, 20):
        y = margin_top + plot_height - (p / 100.0) * plot_height
        svg_lines.append(
            f'  <line x1="{margin_left}" y1="{y:.1f}" x2="{width - margin_right}" y2="{y:.1f}" '
            'stroke="#334155" stroke-dasharray="4" />'
        )
        svg_lines.append(
            f'  <text x="{margin_left - 10}" y="{y + 4:.1f}" fill="#64748b" '
            f'font-size="11" text-anchor="end">{p}%</text>'
        )

    svg_lines.append("  <!-- Clusters de Barras -->")
    for c_idx, (m_key, m_label, _) in enumerate(metric_keys):
        c_x = margin_left + c_idx * cluster_width + cluster_width / 2
        for b_idx, (method_id, _, color) in enumerate(methods):
            val = report["methods"][method_id].get(m_key)
            val_pct = (val or 0.0) * 100.0
            b_height = (val_pct / 100.0) * plot_height
            b_x = c_x + (b_idx - 1) * (bar_width + 4) - bar_width / 2
            b_y = margin_top + plot_height - b_height

            # Barra
            svg_lines.append(
                f'  <rect x="{b_x:.1f}" y="{b_y:.1f}" width="{bar_width}" '
                f'height="{b_height:.1f}" rx="4" fill="{color}" />'
            )
            # Valor textual acima da barra
            val_text = f"{val_pct:.1f}%" if val is not None else "N/A"
            svg_lines.append(
                f'  <text x="{b_x + bar_width / 2:.1f}" y="{b_y - 6:.1f}" fill="{color}" '
                f'font-size="11" font-weight="600" text-anchor="middle">{val_text}</text>'
            )

        # Label da métrica
        svg_lines.append(
            f'  <text x="{c_x:.1f}" y="{margin_top + plot_height + 25}" fill="#cbd5e1" '
            f'font-size="12" font-weight="600" text-anchor="middle">{m_label}</text>'
        )

    # Legenda
    leg_y = margin_top + plot_height + 58
    svg_lines.append("  <!-- Legenda -->")
    svg_lines.append(f'  <g transform="translate({margin_left}, {leg_y})">')
    for idx, (_, label, color) in enumerate(methods):
        lx = idx * 220 + 80
        svg_lines.append(
            f'    <rect x="{lx}" y="0" width="14" height="14" rx="3" fill="{color}" />'
        )
        svg_lines.append(
            f'    <text x="{lx + 22}" y="12" fill="#e2e8f0" font-size="13" '
            f'font-weight="500">{label}</text>'
        )
    svg_lines.append("  </g>")

    # Cards de Latência Média
    card_y = leg_y + 36
    svg_lines.append("  <!-- Painel de Latência -->")
    svg_lines.append(
        f'  <rect x="{margin_left}" y="{card_y}" width="{chart_width}" height="76" rx="8" '
        'fill="#1e293b" stroke="#334155" />'
    )
    svg_lines.append(
        f'  <text x="{margin_left + 20}" y="{card_y + 26}" fill="#94a3b8" '
        'font-size="11" font-weight="600" letter-spacing="1">LATÊNCIA MÉDIA POR REQUISIÇÃO</text>'
    )

    card_col_w = chart_width / 3
    for idx, (m_id, m_label, color) in enumerate(methods):
        col_x = margin_left + idx * card_col_w + 20
        lat_val = report["methods"][m_id].get("latency_mean_ms")
        lat_str = f"{lat_val:.0f} ms" if lat_val else "—"
        svg_lines.append(
            f'  <text x="{col_x}" y="{card_y + 54}" fill="{color}" font-size="18" '
            f'font-weight="700">{lat_str} <tspan fill="#94a3b8" font-size="12" '
            f'font-weight="400">({m_label})</tspan></text>'
        )

    svg_lines.append("</svg>\n")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(svg_lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="Gabarito da issue #20.")
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_RESULTS, help="Arquivo de resultados comparativos."
    )
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=DEFAULT_REPORT_MD)
    parser.add_argument("--chart-svg", type=Path, default=DEFAULT_CHART_SVG)
    parser.add_argument(
        "--provider",
        choices=["litellm", "ollama", "mock"],
        default=None,
        help=(
            "Provedor LLM: litellm (padrão; qualquer modelo pela camada do app, a mesma do "
            "/v1/chat/generate), ollama (cliente direto) ou mock determinístico."
        ),
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=(
            "Modelo no formato do LiteLLM (ex.: ollama/qwen2.5, openai/gpt-4o-mini). "
            "Padrão: LLM_MODEL do api/.env."
        ),
    )
    parser.add_argument("--temperature", type=float, default=0.1, help="Temperatura de amostragem.")
    parser.add_argument(
        "--timeout", type=float, default=120.0, help="Timeout em segundos para o LLM."
    )
    parser.add_argument("--limit", type=int, default=None, help="Limita o número de casos.")
    args = parser.parse_args(argv)

    try:
        cases = load_cases(args.cases)
        if args.limit:
            cases = cases[: args.limit]

        # Mesma camada de modelos do app: o benchmark mede o que o usuário realmente usa.
        provider_name = args.provider or "litellm"
        if provider_name == "ollama":
            from app.clients.ollama_provider import OllamaProvider

            llm: LLMProvider = OllamaProvider(model=args.model, timeout=args.timeout)
        elif provider_name == "litellm":
            from app.clients.litellm_provider import LiteLLMProvider

            llm = LiteLLMProvider(model=args.model, timeout=args.timeout)
        else:
            llm = get_llm_provider(provider_name=provider_name, model_name=args.model)

        print(
            f"Iniciando benchmark: {len(cases)} casos | "
            f"Provedor: {provider_name} | Modelo: {getattr(llm, 'model', args.model)}"
        )
        print("Carregando e indexando corpus unificado (22 fontes)...")
        retriever = UnifiedCorpusRetriever()

        raw_results = asyncio.run(
            run_benchmark(cases, llm, retriever, temperature=args.temperature)
        )

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(raw_results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Resultados brutos salvos em: {args.output}")

        # Avaliação das métricas consolidadas
        print("Calculando métricas comparativas...")
        raw_sources = {
            name: path.read_text(encoding="utf-8") for name, (_, path) in sources().items()
        }
        report = evaluate_comparison(cases, raw_results, sources=raw_sources)

        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Relatório JSON salvo em: {args.report_json}")

        md_content = render_markdown(report)
        args.report_md.parent.mkdir(parents=True, exist_ok=True)
        args.report_md.write_text(md_content, encoding="utf-8")
        print(f"Relatório Markdown salvo em: {args.report_md}")

        # Gráfico comparativo em SVG
        generate_svg_chart(report, args.chart_svg)
        print(f"Gráfico comparativo SVG gerado em: {args.chart_svg}")

        print("\n" + "=" * 60)
        print("RESUMO COMPARATIVO — SEMANA 3")
        print("=" * 60)
        print(md_content)
        return 0
    except Exception as exc:
        import traceback

        traceback.print_exc()
        print(f"Erro na execução do benchmark: {type(exc)} {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
