import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.core.config import settings
from app.domain.models import EvidenceChunk


class RAGService:
    """Mecanismo RAG baseado estritamente em fontes oficiais (BCB, CVM, CFPB).

    Implementa busca de evidências e política ativa de abstenção (ADR 0003).
    """

    def __init__(self, knowledge_base_dir: str | None = None):
        if knowledge_base_dir:
            self.base_dir = Path(knowledge_base_dir)
        else:
            # Caminho padrão a partir de api/app/services
            self.base_dir = Path(__file__).resolve().parents[3] / "research" / "knowledge_base"

        self.chunks: list[EvidenceChunk] = []
        self.vectorizer: TfidfVectorizer | None = None
        self.tfidf_matrix = None
        self._load_knowledge_base()

    def _load_knowledge_base(self) -> None:
        if not self.base_dir.exists():
            return

        chunks: list[EvidenceChunk] = []
        for file_path in self.base_dir.glob("*.txt"):
            content = file_path.read_text(encoding="utf-8")
            file_chunks = self._parse_document(content, file_path.name)
            chunks.extend(file_chunks)

        self.chunks = chunks

        if self.chunks:
            corpus = [c.content for c in self.chunks]
            self.vectorizer = TfidfVectorizer(
                lowercase=True,
                ngram_range=(1, 2),
                stop_words="english",  # or custom portuguese stopwords
            )
            self.tfidf_matrix = self.vectorizer.fit_transform(corpus)

    def _parse_document(self, text: str, filename: str) -> list[EvidenceChunk]:
        chunks: list[EvidenceChunk] = []
        source_name = "Órgão Regulador Oficial"
        doc_title = filename

        # Extrai metadados do cabeçalho se houver
        source_match = re.search(r"FONTE:\s*(.+)", text)
        if source_match:
            source_name = source_match.group(1).strip()

        title_match = re.search(r"TITULO:\s*(.+)", text)
        if title_match:
            doc_title = title_match.group(1).strip()

        # Quebra por seções marcadas com [SEÇÃO ...]
        sections = re.split(r"(\[SEÇÃO\s+\d+:.*?\])", text)
        current_section = "Introdução"

        for part in sections:
            part = part.strip()
            if not part:
                continue
            if part.startswith("[SEÇÃO"):
                current_section = part.replace("[", "").replace("]", "").strip()
            else:
                chunk_id = f"{filename}_{len(chunks) + 1}"
                chunks.append(
                    EvidenceChunk(
                        id=chunk_id,
                        source_name=source_name,
                        document_title=doc_title,
                        section=current_section,
                        content=part,
                    )
                )

        return chunks

    def retrieve_evidence(
        self,
        query: str,
        top_k: int | None = None,
        threshold: float | None = None,
    ) -> list[EvidenceChunk]:
        """Recupera os trechos mais relevantes da base oficial."""
        if not self.vectorizer or self.tfidf_matrix is None or not self.chunks:
            return []

        k = top_k if top_k is not None else settings.RAG_TOP_K
        thresh = threshold if threshold is not None else settings.RAG_SIMILARITY_THRESHOLD

        query_vec = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        ranked_indices = similarities.argsort()[::-1]
        results: list[EvidenceChunk] = []

        for idx in ranked_indices[:k]:
            score = float(similarities[idx])
            if score >= thresh:
                chunk = self.chunks[idx].model_copy()
                chunk.score = round(score, 4)
                results.append(chunk)

        return results

    def answer_query(self, query: str) -> dict[str, object]:
        """Responde a uma consulta financeira com fundamentação e abstenção ativa."""
        evidences = self.retrieve_evidence(query)

        # Regra de Abstenção Ativa (GQ05 e ADR 0003)
        if not evidences:
            return {
                "query": query,
                "answered": False,
                "status": "abstained",
                "answer": (
                    "O Trokim não possui evidências suficientes nas diretrizes oficiais "
                    "(Banco Central do Brasil, CVM ou CFPB) para responder a essa consulta "
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
        )

        return {
            "query": query,
            "answered": True,
            "status": "grounded",
            "answer": grounded_answer,
            "evidences": [ev.model_dump() for ev in evidences],
        }
