"""Pipeline de ingestão da base de conhecimento no banco vetorial.

Lê os .txt oficiais, aplica o parsing de cabeçalho/seção, chunka o conteúdo
de cada seção, gera embeddings densos e grava tudo no VectorStore. A
ingestão é idempotente: o hash do corpus inclui os parâmetros de chunking,
e uma segunda execução sem mudanças não reingere.
"""

import hashlib
import re
from pathlib import Path

from pydantic import BaseModel

from app.core.config import settings
from app.domain.models import EvidenceChunk
from app.models.embedding_model import EmbeddingModel
from app.models.vector_store import VectorStore
from app.services.chunking_service import chunk_text


class IngestionReport(BaseModel):
    documents_read: int
    chunks_generated: int
    dimension: int
    model: str
    corpus_hash: str
    reingested: bool


def compute_corpus_hash(
    knowledge_base_dir: str | Path,
    *,
    max_chars: int | None = None,
    overlap_tokens: int | None = None,
) -> str:
    """SHA-256 dos arquivos .txt ordenados mais a configuração de chunking."""
    max_chars = settings.RAG_CHUNK_MAX_CHARS if max_chars is None else max_chars
    overlap_tokens = settings.RAG_CHUNK_OVERLAP_TOKENS if overlap_tokens is None else overlap_tokens
    digest = hashlib.sha256()
    digest.update(f"chunking:{max_chars}:{overlap_tokens}".encode())
    digest.update(Path(__file__).with_name("chunking_service.py").read_bytes())
    for path in sorted(Path(knowledge_base_dir).glob("*.txt")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def parse_document(
    text: str,
    filename: str,
    *,
    max_chars: int | None = None,
    overlap_tokens: int | None = None,
) -> list[EvidenceChunk]:
    """Extrai metadados do cabeçalho e chunka o conteúdo de cada seção."""
    max_chars = settings.RAG_CHUNK_MAX_CHARS if max_chars is None else max_chars
    overlap_tokens = settings.RAG_CHUNK_OVERLAP_TOKENS if overlap_tokens is None else overlap_tokens
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
            for piece in chunk_text(part, max_chars, overlap_tokens):
                chunks.append(
                    EvidenceChunk(
                        id=f"{filename}_{len(chunks) + 1}",
                        document_id=filename,
                        source_name=source_name,
                        source_url=source_url,
                        document_title=doc_title,
                        section=current_section,
                        content=piece,
                    )
                )

    return chunks


def ingest(
    knowledge_base_dir: str | Path,
    store: VectorStore,
    embedder: EmbeddingModel,
) -> IngestionReport:
    """Ingere os .txt no store; reingere só quando hash ou modelo divergirem."""
    base_dir = Path(knowledge_base_dir)
    corpus_hash = compute_corpus_hash(base_dir)
    files = sorted(base_dir.glob("*.txt"))

    unchanged = (
        store.count() > 0
        and store.get_meta("corpus_hash") == corpus_hash
        and store.get_meta("embedding_model") == embedder.name
    )
    if unchanged:
        return IngestionReport(
            documents_read=len(files),
            chunks_generated=store.count(),
            dimension=embedder.dimension,
            model=embedder.name,
            corpus_hash=corpus_hash,
            reingested=False,
        )

    chunks: list[EvidenceChunk] = []
    for file_path in files:
        chunks.extend(parse_document(file_path.read_text(encoding="utf-8"), file_path.name))

    vectors = embedder.embed_documents(
        [f"{c.document_title}. {c.section}. {c.content}" for c in chunks]
    )
    store.reset()
    store.add(chunks, vectors)
    store.set_meta("corpus_hash", corpus_hash)
    store.set_meta("embedding_model", embedder.name)

    return IngestionReport(
        documents_read=len(files),
        chunks_generated=len(chunks),
        dimension=embedder.dimension,
        model=embedder.name,
        corpus_hash=corpus_hash,
        reingested=True,
    )


def main() -> None:
    from app.clients.fastembed_embeddings import get_default_embedder
    from app.clients.sqlite_vector_store import SQLiteVectorStore

    base_dir = Path(__file__).resolve().parents[3] / "research" / "knowledge_base"
    embedder = get_default_embedder()
    store = SQLiteVectorStore(settings.vector_db_path, dimension=embedder.dimension)
    report = ingest(base_dir, store, embedder)
    print(
        f"documentos={report.documents_read} chunks={report.chunks_generated} "
        f"modelo={report.model} dimensão={report.dimension} "
        f"hash={report.corpus_hash} reingerido={report.reingested}"
    )


if __name__ == "__main__":
    main()
