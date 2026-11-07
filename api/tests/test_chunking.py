import pytest

from app.services.chunking_service import chunk_text


def test_texto_curto_permanece_inteiro():
    text = "Guarde dinheiro para emergências. Planeje despesas."
    assert chunk_text(text) == [text]


def test_texto_vazio_nao_gera_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_janelas_respeitam_limite_e_sobreposicao_de_frases():
    sentences = [f"Reserva numero {i} protege despesas." for i in range(20)]
    chunks = chunk_text(" ".join(sentences), max_chars=110, overlap_tokens=5)
    assert len(chunks) > 1
    assert all(len(chunk) <= 110 for chunk in chunks)
    for previous, current in zip(chunks, chunks[1:], strict=False):
        last_sentence = previous[previous.rfind(".", 0, len(previous) - 1) + 1 :].strip()
        assert current.startswith(last_sentence)
        assert len(last_sentence.split()) <= 5
    assert all(any(sentence in chunk for chunk in chunks) for sentence in sentences)


def test_frase_longa_quebra_apenas_entre_palavras():
    words = [f"palavra{i}" for i in range(100)]
    chunks = chunk_text(" ".join(words), max_chars=65, overlap_tokens=0)
    assert len(chunks) > 1
    assert all(len(chunk) <= 65 for chunk in chunks)
    assert [word for chunk in chunks for word in chunk.split()] == words


def test_frase_longa_com_sobreposicao_nao_perde_palavras():
    words = [f"termo{i}" for i in range(80)]
    chunks = chunk_text(" ".join(words), max_chars=70, overlap_tokens=3)
    assert len(chunks) > 1
    assert all(len(chunk) <= 70 for chunk in chunks)
    assert set(word for chunk in chunks for word in chunk.split()) == set(words)


@pytest.mark.parametrize("size", [49, 50, 51])
def test_limite_exato_sem_cortar_palavras(size):
    text = "a " * 24 + "b"
    chunks = chunk_text(text, max_chars=size, overlap_tokens=0)
    assert chunks == [text]


@pytest.mark.parametrize("max_chars,overlap_tokens", [(0, 50), (-1, 0), (500, -1)])
def test_parametros_invalidos_sao_rejeitados(max_chars, overlap_tokens):
    with pytest.raises(ValueError):
        chunk_text("Texto de teste.", max_chars=max_chars, overlap_tokens=overlap_tokens)


def test_palavra_maior_que_janela_e_rejeitada_sem_corte():
    with pytest.raises(ValueError, match="palavra excede"):
        chunk_text("palavramuitolonga", max_chars=5)


def test_sobreposicao_padrao_nao_excede_cinquenta_palavras():
    sentences = [f"Marcador{i} " + "reserva " * 9 + "segura." for i in range(30)]
    chunks = chunk_text(" ".join(sentences), max_chars=500)
    assert len(chunks) > 1
    for previous, current in zip(chunks, chunks[1:], strict=False):
        left, right = previous.split(), current.split()
        overlaps = [n for n in range(1, min(len(left), len(right)) + 1) if left[-n:] == right[:n]]
        assert overlaps
        assert max(overlaps) <= 50
