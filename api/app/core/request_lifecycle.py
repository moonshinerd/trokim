"""Ciclo de vida de operações assíncronas vinculadas à conexão HTTP."""

import asyncio
from collections.abc import Coroutine

from fastapi import HTTPException, Request


async def _wait_for_disconnect(request: Request) -> None:
    while not await request.is_disconnected():
        await asyncio.sleep(0.05)


async def run_while_connected[T](request: Request, operation: Coroutine[None, None, T]) -> T:
    """Cancela e aguarda a limpeza da operação quando o cliente se desconecta."""
    work = asyncio.create_task(operation)
    disconnect = asyncio.create_task(_wait_for_disconnect(request))
    try:
        done, _ = await asyncio.wait((work, disconnect), return_when=asyncio.FIRST_COMPLETED)
        if work in done:
            return await work
        await disconnect
        raise HTTPException(status_code=499, detail="Solicitação cancelada pelo cliente.")
    finally:
        for task in (work, disconnect):
            if not task.done():
                task.cancel()
        await asyncio.gather(work, disconnect, return_exceptions=True)
