import pytest

from app.clients.sqlite_vector_store import SQLiteVectorStore
from app.domain.models import EvidenceChunk


def make_chunk(index):
    return EvidenceChunk(
        id=f"documento{index}.txt_1",
        document_id=f"documento{index}.txt",
        source_name="Banco Central do Brasil",
        source_url="https://www.bcb.gov.br/",
        document_title=f"Documento {index}",
        section="SEÇÃO 1: Planejamento",
        content=f"Conteúdo institucional {index}.",
    )


def test_ordem_por_proximidade_e_metadados(tmp_path):
    store = SQLiteVectorStore(tmp_path / "vectors.db", dimension=2)
    chunks = [make_chunk(i) for i in range(3)]
    store.add(chunks, [[1.0, 0.0], [0.8, 0.6], [0.0, 1.0]])
    assert store.count() == 3
    results = store.search([1.0, 0.0], 3)
    assert [chunk.id for chunk, _ in results] == [chunk.id for chunk in chunks]
    assert results[0][0].model_dump() == chunks[0].model_dump()
    assert [score for _, score in results] == pytest.approx([1.0, 0.8, 0.0], abs=1e-5)


def test_reset_limpa_indice_e_metadados(tmp_path):
    store = SQLiteVectorStore(tmp_path / "reset.db", dimension=2)
    store.add([make_chunk(0)], [[1.0, 0.0]])
    store.set_meta("corpus_hash", "hash-antigo")
    store.reset()
    assert store.count() == 0
    assert store.search([1.0, 0.0], 3) == []
    assert store.get_meta("corpus_hash") is None


def test_persistencia_ao_reabrir_arquivo(tmp_path):
    path = tmp_path / "persistent.db"
    store = SQLiteVectorStore(path, dimension=2)
    chunk = make_chunk(1)
    store.add([chunk], [[0.0, 1.0]])
    store.set_meta("model_name", "modelo-local")
    reopened = SQLiteVectorStore(path, dimension=2)
    assert reopened.count() == 1
    assert reopened.get_meta("model_name") == "modelo-local"
    assert reopened.search([0.0, 1.0], 1)[0][0].model_dump() == chunk.model_dump()
    assert reopened.get_meta("inexistente") is None


def test_topk_e_consulta_em_store_vazio(tmp_path):
    store = SQLiteVectorStore(tmp_path / "empty.db", dimension=2)
    assert store.search([1.0, 0.0], 5) == []
    store.add([make_chunk(0)], [[1.0, 0.0]])
    assert len(store.search([1.0, 0.0], 1)) == 1
