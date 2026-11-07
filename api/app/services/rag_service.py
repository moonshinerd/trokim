import re
import unicodedata
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.pipeline import FeatureUnion

from app.clients.fastembed_embeddings import get_default_embedder
from app.clients.sqlite_vector_store import SQLiteVectorStore
from app.core.config import settings
from app.domain.models import EvidenceChunk
from app.models.embedding_model import EmbeddingModel
from app.models.vector_store import VectorStore
from app.services.ingestion_service import compute_corpus_hash, ingest


class RAGService:
    """Mecanismo RAG baseado estritamente em fontes oficiais (BCB, CVM, CFPB, ANPD).

    Implementa busca de evidências e política ativa de abstenção (ADR 0003).
    A busca é híbrida: score = alpha * cosseno_denso + (1 - alpha) * cosseno_tfidf.
    """

    def __init__(
        self,
        knowledge_base_dir: str | None = None,
        *,
        top_k: int | None = None,
        threshold: float | None = None,
        alpha: float | None = None,
        embedder: EmbeddingModel | None = None,
        store: VectorStore | None = None,
    ):
        self.top_k = settings.RAG_TOP_K if top_k is None else top_k
        self.threshold = settings.RAG_SIMILARITY_THRESHOLD if threshold is None else threshold
        self.alpha = settings.RAG_HYBRID_ALPHA if alpha is None else alpha
        if knowledge_base_dir:
            self.base_dir = Path(knowledge_base_dir)
        else:
            # Caminho padrão a partir de api/app/services
            self.base_dir = Path(__file__).resolve().parents[3] / "research" / "knowledge_base"

        self.embedder = embedder or get_default_embedder()
        self.store = store or SQLiteVectorStore(
            settings.vector_db_path, dimension=self.embedder.dimension
        )
        if self.base_dir.exists() and self._needs_ingestion():
            ingest(self.base_dir, self.store, self.embedder)

        self.chunks: list[EvidenceChunk] = self.store.all()
        self.vectorizer: FeatureUnion | None = None
        self.tfidf_matrix = None
        self._fit_lexical_index()

    def _needs_ingestion(self) -> bool:
        return (
            self.store.count() == 0
            or self.store.get_meta("corpus_hash") != compute_corpus_hash(self.base_dir)
            or self.store.get_meta("embedding_model") != self.embedder.name
        )

    def _fit_lexical_index(self) -> None:
        if not self.chunks:
            return

        corpus = [f"{c.document_title}. {c.section}. {c.content}" for c in self.chunks]
        # Palavras preservam conceitos; caracteres toleram flexões em português.
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

    def retrieve_evidence(
        self,
        query: str,
        top_k: int | None = None,
        threshold: float | None = None,
    ) -> list[EvidenceChunk]:
        """Recupera os trechos mais relevantes da base oficial."""
        if not self.vectorizer or self.tfidf_matrix is None or not self.chunks:
            return []

        k = top_k if top_k is not None else self.top_k
        thresh = threshold if threshold is not None else self.threshold

        if k <= 0 or not query.strip():
            return []

        query_vec = self.vectorizer.transform([query])
        tfidf_sims = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        dense_hits = self.store.search(self.embedder.embed_query(query), self.store.count())
        dense_sims = {chunk.id: similarity for chunk, similarity in dense_hits}

        scored = [
            (
                idx,
                self.alpha * dense_sims.get(chunk.id, 0.0)
                + (1 - self.alpha) * float(tfidf_sims[idx]),
            )
            for idx, chunk in enumerate(self.chunks)
        ]
        scored.sort(key=lambda item: item[1], reverse=True)

        results: list[EvidenceChunk] = []
        seen_documents: set[str] = set()
        for idx, score in scored:
            if score <= 0 or score < thresh:
                break
            chunk = self.chunks[idx]
            document_key = chunk.document_id or chunk.id
            if document_key in seen_documents:
                continue
            seen_documents.add(document_key)
            result = chunk.model_copy()
            result.score = round(score, 4)
            results.append(result)
            if len(results) == k:
                break

        return results

    @staticmethod
    def _outside_scope(query: str) -> bool:
        """Limita o protótipo a orientação educacional, sem acesso a dados de contas.

        Regras de intenção conservadoras; não constituem proteção geral contra
        ataques. Menções educacionais a golpes, senhas ou música são permitidas.
        """
        normalized = unicodedata.normalize("NFKD", query).encode("ascii", "ignore").decode().lower()
        patterns = (
            r"\b(escreva|crie|faca|conte|componha|gere)\b.*\b(poema|poesia|musica|conto|roteiro|piada)\b",
            r"\b(ignore|desconsidere|esqueca)\b.*\b(fontes|regras|instrucoes|diretrizes)\b",
            r"\b(saldo|limite)\b.*\b(minha|meu)\b",
            r"\b(acesse|consulte|revele|mostre)\b.*\b(conta|senha|cpf|extrato)\b",
            r"\b(quanto|qual)\b.*\b(tenho|gastei|recebi)\b",
            r"\b(garanta|garantir)\b.*\b(lucro|retorno|dinheiro)\b",
            r"\b(diga|indique|escolha|recomende)\b.*\b(acao|cripto|criptomoeda)\b.*\b(comprar|lucro)\b",
            r"\b(descobrir|roubar|obter|revelar)\b.*\b(senha|cpf)\b",
            r"\b(bolo|futebol|copa do mundo|remedio|gripe|horoscopo)\b",
            r"\b(escreva|gere|crie)\b.*\b(codigo|script|programa)\b",
        )
        return any(re.search(pattern, normalized) for pattern in patterns)

    def answer_query(self, query: str) -> dict[str, object]:
        """Responde a uma consulta financeira com fundamentação e abstenção ativa."""
        evidences = [] if self._outside_scope(query) else self.retrieve_evidence(query)

        # Regra de Abstenção Ativa (GQ05 e ADR 0003)
        if not evidences:
            return {
                "query": query,
                "answered": False,
                "status": "abstained",
                "answer": (
                    "O Trokim não possui evidências suficientes nas diretrizes oficiais "
                    "(Banco Central do Brasil, CVM, CFPB ou ANPD) para responder a essa consulta "
                    "com segurança. Para sua proteção financeira, recomendamos consultar "
                    "canais oficiais regulamentados."
                ),
                "evidences": [],
            }

        # Resposta orientada às fontes
        primary_ev = evidences[0]
        grounded_answer = (
            f"Com base nas diretrizes do {primary_ev.source_name} ({primary_ev.section}):\n\n"
            f"{primary_ev.content}\n\n"
            f"Fonte oficial citada: {primary_ev.document_title}."
            + (f"\nURL: {primary_ev.source_url}" if primary_ev.source_url else "")
        )

        return {
            "query": query,
            "answered": True,
            "status": "grounded",
            "answer": grounded_answer,
            "evidences": [ev.model_dump() for ev in evidences],
        }
