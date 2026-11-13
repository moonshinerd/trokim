"""Validação do cancelamento de geração sem rede, modelo ou embeddings."""

import asyncio

import pytest
from fastapi import HTTPException, Request

from app.core.request_lifecycle import run_while_connected


def connection(messages: asyncio.Queue) -> Request:
    return Request({"type": "http", "method": "POST", "path": "/"}, receive=messages.get)


@pytest.mark.asyncio
async def test_desconexao_aguarda_limpeza_antes_de_nova_geracao():
    messages = asyncio.Queue()
    started = asyncio.Event()
    cleaned = asyncio.Event()
    active = 0

    async def generate():
        nonlocal active
        active += 1
        started.set()
        try:
            await asyncio.Future()
        finally:
            active -= 1
            cleaned.set()

    first = asyncio.create_task(run_while_connected(connection(messages), generate()))
    await asyncio.wait_for(started.wait(), timeout=1)
    await messages.put({"type": "http.disconnect"})
    with pytest.raises(HTTPException) as error:
        await asyncio.wait_for(first, timeout=1)
    assert error.value.status_code == 499
    assert cleaned.is_set()
    assert active == 0

    async def retry():
        assert active == 0
        return "Resposta da nova tentativa"

    assert await run_while_connected(connection(asyncio.Queue()), retry()) == (
        "Resposta da nova tentativa"
    )


@pytest.mark.asyncio
async def test_sucesso_cancela_monitor_de_conexao():
    async def generate():
        return "Resposta fundamentada"

    assert (
        await run_while_connected(connection(asyncio.Queue()), generate())
        == "Resposta fundamentada"
    )


@pytest.mark.asyncio
async def test_erro_do_modelo_preservado():
    async def generate():
        raise RuntimeError("Modelo indisponível")

    with pytest.raises(RuntimeError, match="Modelo indisponível"):
        await run_while_connected(connection(asyncio.Queue()), generate())


@pytest.mark.asyncio
async def test_cancelamento_externo_nao_deixa_geracao_pendente():
    started = asyncio.Event()
    cleaned = asyncio.Event()

    async def generate():
        started.set()
        try:
            await asyncio.Future()
        finally:
            cleaned.set()

    task = asyncio.create_task(run_while_connected(connection(asyncio.Queue()), generate()))
    await asyncio.wait_for(started.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cleaned.is_set()


@pytest.mark.asyncio
async def test_endpoint_cancela_geracao_ao_desconectar_e_permite_nova_tentativa(monkeypatch):
    import json
    from unittest.mock import AsyncMock

    import httpx

    from app.main import app
    from app.routers.v1.chat import get_generation_service
    from app.services.generation_service import GenerationResult

    started = asyncio.Event()
    disconnected = asyncio.Event()
    cleaned = asyncio.Event()
    active = 0

    async def generate(*args, **kwargs):
        nonlocal active
        active += 1
        started.set()
        try:
            await asyncio.Future()
        finally:
            active -= 1
            cleaned.set()

    service = AsyncMock()
    service.generate_answer.side_effect = generate
    monkeypatch.setitem(app.dependency_overrides, get_generation_service, lambda: service)
    body = json.dumps({"message": "Reserva?", "mode": "grounded"}).encode()
    body_sent = False
    sent = []

    async def receive():
        nonlocal body_sent
        if not body_sent:
            body_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        await disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/chat/generate",
        "query_string": b"",
        "headers": [(b"content-type", b"application/json")],
        "scheme": "http",
        "http_version": "1.1",
    }
    first = asyncio.create_task(app(scope, receive, send))
    await asyncio.wait_for(started.wait(), timeout=1)
    disconnected.set()
    await asyncio.wait_for(first, timeout=1)
    assert cleaned.is_set()
    assert active == 0
    assert sent[0]["status"] == 499

    async def retry(*args, **kwargs):
        assert active == 0
        return GenerationResult(
            query="Reserva?",
            answered=False,
            status="abstained",
            mode="grounded",
            model="mock",
            answer="Sem evidências suficientes.",
        )

    service.generate_answer.side_effect = retry
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/v1/chat/generate", json={"message": "Reserva?"})
    assert response.status_code == 200
    assert response.json()["status"] == "abstained"
