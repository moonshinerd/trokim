"""Quebra de texto em janelas com sobreposição para indexação vetorial."""

import re

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str, max_chars: int) -> list[str]:
    pieces: list[str] = []
    for sentence in _SENTENCE_BOUNDARY.split(text.strip()):
        words: list[str] = []
        for word in sentence.split():
            if len(word) > max_chars:
                raise ValueError("Uma palavra excede max_chars; não é possível cortá-la.")
            if words and len(" ".join([*words, word])) > max_chars:
                pieces.append(" ".join(words))
                words = []
            words.append(word)
        if words:
            pieces.append(" ".join(words))
    return pieces


def _overlap_seed(sentences: list[str], overlap_tokens: int) -> list[str]:
    """Seleciona frases finais; token é aproximado por palavra separada por espaço."""
    seed: list[str] = []
    words = 0
    for sentence in reversed(sentences):
        count = len(sentence.split())
        if words + count > overlap_tokens:
            break
        seed.insert(0, sentence)
        words += count
    return seed


def chunk_text(text: str, max_chars: int = 500, overlap_tokens: int = 50) -> list[str]:
    """Monta janelas por frase, repetindo até overlap_tokens palavras das frases finais.

    Token é aproximado por palavra separada por espaço. Frases maiores que a janela
    são divididas entre palavras. A sobreposição diminui se necessário para acomodar
    conteúdo novo dentro de max_chars; uma palavra maior que a janela é rejeitada.
    """
    if max_chars <= 0 or overlap_tokens < 0:
        raise ValueError("max_chars deve ser positivo e overlap_tokens não negativo.")
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    for sentence in _split_sentences(text, max_chars):
        if current and len(" ".join([*current, sentence])) > max_chars:
            chunks.append(" ".join(current))
            current = _overlap_seed(current, overlap_tokens)
            while current and len(" ".join([*current, sentence])) > max_chars:
                current.pop(0)
        current.append(sentence)
    if current:
        chunks.append(" ".join(current))
    return chunks
