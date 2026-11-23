"""Portas de OCR e visão (ADR 0021): contrato, fábrica, consentimento remoto e privacidade."""

import io
import json
import logging
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.clients import litellm_vision_provider as lvp
from app.clients.litellm_vision_provider import LiteLLMVisionProvider, is_remote_model
from app.clients.mock_vision import MockOcrProvider, MockVisionProvider
from app.clients.rapidocr_provider import RapidOcrProvider
from app.clients.vision_factory import (
    RemoteVisionNotAllowedError,
    get_ocr_provider,
    get_vision_provider,
)
from app.core.config import settings
from app.models.vision_provider import OcrProvider, OcrResult, OcrWord, VisionProvider


def _png(texto: str = "TOTAL R$ 123,45") -> bytes:
    imagem = Image.new("RGB", (640, 160), "white")
    ImageDraw.Draw(imagem).text((20, 50), texto, fill="black", font=ImageFont.load_default(48))
    saida = io.BytesIO()
    imagem.save(saida, format="PNG")
    return saida.getvalue()


# --- contrato -------------------------------------------------------------------------------


def test_adaptadores_cumprem_as_portas():
    assert isinstance(MockOcrProvider(), OcrProvider)
    assert isinstance(RapidOcrProvider(), OcrProvider)
    assert isinstance(MockVisionProvider(), VisionProvider)
    assert isinstance(LiteLLMVisionProvider(model="ollama/qwen2.5vl"), VisionProvider)


def test_resultado_do_ocr_junta_texto_e_calcula_confianca_media():
    resultado = OcrResult(
        words=[OcrWord(text="A", confidence=0.9), OcrWord(text="B", confidence=0.5)],
        engine="mock",
    )
    assert resultado.text == "A\nB"
    assert resultado.mean_confidence == pytest.approx(0.7)
    assert OcrResult(engine="mock").mean_confidence is None


async def test_mocks_sao_deterministicos():
    ocr = await MockOcrProvider([("VALOR 10,00", 0.8)]).read(b"x")
    assert ocr.text == "VALOR 10,00" and ocr.engine == "mock"
    visao = await MockVisionProvider(fields={"amount": "10,00"}).extract(b"x", "leia")
    assert json.loads(visao.content) == {"amount": "10,00"}


# --- fábrica e consentimento ----------------------------------------------------------------


def test_visao_vem_desligada_por_padrao():
    assert settings.VISION_PROVIDER == "none"
    assert settings.VISION_ALLOW_REMOTE is False
    assert get_vision_provider() is None


def test_trocar_o_motor_e_so_configuracao():
    assert get_ocr_provider("mock").name == "mock"
    assert get_ocr_provider("rapidocr").name == "rapidocr"
    assert get_vision_provider("mock").name == "mock"
    assert get_vision_provider("litellm", "ollama/qwen2.5vl").model == "ollama/qwen2.5vl"
    with pytest.raises(ValueError, match="OCR_PROVIDER"):
        get_ocr_provider("inexistente")
    with pytest.raises(ValueError, match="VISION_PROVIDER"):
        get_vision_provider("inexistente")


@pytest.mark.parametrize(
    ("modelo", "base", "remoto"),
    [
        ("ollama/qwen2.5vl", None, False),
        ("ollama/qwen2.5vl", "http://localhost:11434", False),
        ("ollama/qwen2.5vl", "http://127.0.0.1:11434", False),
        ("ollama/qwen2.5vl", "http://host.docker.internal:11434", False),
        ("ollama/qwen2.5vl", "http://192.168.0.9:11434", True),
        ("openrouter/qwen/qwen2.5-vl-72b-instruct", None, True),
        ("openai/gpt-4o", None, True),
    ],
)
def test_detecta_modelo_que_sai_do_aparelho(modelo, base, remoto):
    assert is_remote_model(modelo, base) is remoto


def test_modelo_remoto_exige_consentimento():
    with pytest.raises(RemoteVisionNotAllowedError, match="VISION_ALLOW_REMOTE"):
        get_vision_provider("litellm", "openrouter/qwen/qwen2.5-vl-72b-instruct")
    liberado = get_vision_provider(
        "litellm", "openrouter/qwen/qwen2.5-vl-72b-instruct", allow_remote=True
    )
    assert liberado.is_remote is True


def test_consentimento_vem_da_configuracao(monkeypatch):
    monkeypatch.setattr(settings, "VISION_ALLOW_REMOTE", True)
    assert get_vision_provider("litellm", "openrouter/x/y").is_remote is True


# --- adaptador LiteLLM ----------------------------------------------------------------------


async def test_litellm_envia_a_imagem_em_base64_e_devolve_o_json(monkeypatch):
    enviado = {}

    async def falso(**kwargs):
        enviado.update(kwargs)
        mensagem = SimpleNamespace(content=' {"amount": "10,00"} ')
        return SimpleNamespace(
            choices=[SimpleNamespace(message=mensagem)],
            usage=SimpleNamespace(prompt_tokens=7, completion_tokens=3),
        )

    monkeypatch.setattr(lvp.litellm, "acompletion", falso)
    provedor = LiteLLMVisionProvider(model="ollama/qwen2.5vl", api_base="", api_key="")
    resultado = await provedor.extract(_png(), "Leia o comprovante.", {"amount": "string"})

    partes = enviado["messages"][0]["content"]
    assert partes[0]["type"] == "text" and "Leia o comprovante." in partes[0]["text"]
    assert partes[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert enviado["temperature"] == 0.0
    assert resultado.content == '{"amount": "10,00"}'
    assert (resultado.prompt_tokens, resultado.completion_tokens) == (7, 3)


async def test_erro_do_modelo_nao_vaza_imagem_nem_conteudo(monkeypatch, caplog):
    async def falha(**kwargs):
        raise ConnectionError("falhou com data:image/png;base64,AAAA e SALDO 999,99")

    monkeypatch.setattr(lvp.litellm, "acompletion", falha)
    provedor = LiteLLMVisionProvider(model="ollama/qwen2.5vl", api_base="", api_key="")
    with caplog.at_level(logging.DEBUG), pytest.raises(RuntimeError) as erro:
        await provedor.extract(_png(), "leia")
    assert "base64" not in str(erro.value) and "999,99" not in str(erro.value)
    assert "base64" not in caplog.text and "999,99" not in caplog.text


# --- OCR local de verdade -------------------------------------------------------------------


async def test_ocr_local_le_uma_imagem_sintetica():
    pytest.importorskip("rapidocr_onnxruntime")
    resultado = await RapidOcrProvider().read(_png("TOTAL 123,45"))
    texto = resultado.text.replace(" ", "")
    assert "123,45" in texto
    assert resultado.engine == "rapidocr"
    assert resultado.mean_confidence and resultado.mean_confidence > 0.5
    assert all(word.box for word in resultado.words)


async def test_ocr_em_imagem_em_branco_nao_inventa_texto():
    pytest.importorskip("rapidocr_onnxruntime")
    branco = io.BytesIO()
    Image.new("RGB", (300, 120), "white").save(branco, format="PNG")
    resultado = await RapidOcrProvider().read(branco.getvalue())
    assert resultado.words == []
    assert resultado.mean_confidence is None
