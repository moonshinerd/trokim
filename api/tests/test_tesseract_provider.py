"""Adaptador do Tesseract (ADR 0021): parser do TSV e caminho do subprocesso com binário falso."""

import asyncio
import shutil
import stat

import pytest

from app.clients.rapidocr_provider import OcrUnavailableError
from app.clients.tesseract_provider import TesseractProvider, parse_tsv
from app.clients.vision_factory import get_ocr_provider

HEADER = (
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"
)
TSV = "\n".join(
    [
        HEADER,
        "1\t1\t0\t0\t0\t0\t0\t0\t800\t600\t-1\t",
        "5\t1\t1\t1\t1\t1\t10\t20\t100\t30\t96.5\tPix",
        "5\t1\t1\t1\t1\t2\t120\t20\t80\t30\t88\tR$",
        "5\t1\t1\t1\t1\t3\t210\t20\t90\t30\t-1\tlixo",  # sem confiança
        "5\t1\t1\t1\t1\t4\t310\t20\t90\t30\t90\t   ",  # texto vazio
        "5\t1\t1\t1\t1\t5\tabc\t20\t90\t30\t90\tquebrada",  # número inválido
        "linha curta",
    ]
)


def _run(coro):
    return asyncio.run(coro)


def test_parse_tsv_so_palavras_validas():
    words = parse_tsv(TSV)
    assert [w.text for w in words] == ["Pix", "R$"]
    assert words[0].confidence == pytest.approx(0.965)
    assert words[0].box == (10, 20, 110, 50)


def test_sem_binario_avisa_com_clareza():
    provider = TesseractProvider(binary="")
    with pytest.raises(OcrUnavailableError, match="Tesseract"):
        _run(provider.read(b"imagem"))


def _fake(tmp_path, body: str) -> str:
    script = tmp_path / "tesseract"
    script.write_text("#!/bin/sh\n" + body)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def test_subprocesso_le_tsv_e_nao_vaza_stderr(tmp_path):
    out = tmp_path / "saida.tsv"
    out.write_text(TSV)
    binary = _fake(tmp_path, f"cat >/dev/null\ncat '{out}'\n")
    result = _run(TesseractProvider(binary=binary, lang="por").read(b"png"))
    assert result.engine == "tesseract" and result.text == "Pix\nR$"
    falha = _fake(tmp_path, "cat >/dev/null\necho 'SEGREDO 123' >&2\nexit 3\n")
    with pytest.raises(OcrUnavailableError) as err:
        _run(TesseractProvider(binary=falha).read(b"png"))
    assert "SEGREDO" not in str(err.value) and "3" in str(err.value)


def test_fabrica_conhece_tesseract():
    assert get_ocr_provider("tesseract").name == "tesseract"
    with pytest.raises(ValueError, match="tesseract"):
        get_ocr_provider("outro")


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract não instalado")
def test_tesseract_real_le_uma_imagem():
    from io import BytesIO

    from PIL import Image, ImageDraw

    img = Image.new("RGB", (400, 80), "white")
    ImageDraw.Draw(img).text((10, 20), "TROKIM 123", fill="black")
    buf = BytesIO()
    img.save(buf, "PNG")
    result = _run(TesseractProvider().read(buf.getvalue()))
    assert result.engine == "tesseract"
