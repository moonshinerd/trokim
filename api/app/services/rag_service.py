import re
import unicodedata
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.pipeline import FeatureUnion

from app.core.config import settings
from app.domain.models import EvidenceChunk


class RAGService:
    """Mecanismo RAG baseado estritamente em fontes oficiais (BCB, CVM, CFPB, ANPD).

    Implementa busca de evidências e política ativa de abstenção (ADR 0003).
    """

    def __init__(
        self,
        knowledge_base_dir: str | None = None,
        *,
        top_k: int | None = None,
        threshold: float | None = None,
    ):
        self.top_k = settings.RAG_TOP_K if top_k is None else top_k
        self.threshold = settings.RAG_SIMILARITY_THRESHOLD if threshold is None else threshold
        if knowledge_base_dir:
            self.base_dir = Path(knowledge_base_dir)
        else:
            # Caminho padrão a partir de api/app/services
            self.base_dir = Path(__file__).resolve().parents[3] / "research" / "knowledge_base"

        self.chunks: list[EvidenceChunk] = []
        self.vectorizer: FeatureUnion | None = None
        self.tfidf_matrix = None
        self._load_knowledge_base()

    def _load_knowledge_base(self) -> None:
        if not self.base_dir.exists():
            return

        chunks: list[EvidenceChunk] = []
        for file_path in sorted(self.base_dir.glob("*.txt")):
            content = file_path.read_text(encoding="utf-8")
            file_chunks = self._parse_document(content, file_path.name)
            chunks.extend(file_chunks)

        self.chunks = chunks

        if self.chunks:
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

        url_match = re.search(r"^URL:\s*(https://\S+)", text, re.MULTILINE)
        source_url = url_match.group(1) if url_match else None

        # Quebra por seções marcadas com [SEÇÃO ...]
        sections = re.split(r"(\[SEÇÃO\s+\d+:.*?\])", text)
        current_section = "Introdução"

        for part in sections:
            part = part.strip()
            if not part:
                continue
            if part.startswith("[SEÇÃO"):
                current_section = part.replace("[", "").replace("]", "").strip()
            elif current_section != "Introdução":
                chunk_id = f"{filename}_{len(chunks) + 1}"
                chunks.append(
                    EvidenceChunk(
                        id=chunk_id,
                        source_name=source_name,
                        source_url=source_url,
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

        k = top_k if top_k is not None else self.top_k
        thresh = threshold if threshold is not None else self.threshold

        if k <= 0:
            return []

        query_vec = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        ranked_indices = similarities.argsort()[::-1]
        results: list[EvidenceChunk] = []

        for idx in ranked_indices[:k]:
            score = float(similarities[idx])
            if score > 0 and score >= thresh:
                chunk = self.chunks[idx].model_copy()
                chunk.score = round(score, 4)
                results.append(chunk)

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
