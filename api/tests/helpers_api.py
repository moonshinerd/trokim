from httpx import ASGITransport, AsyncClient

from app.main import app


def cliente() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def enviar(
    client: AsyncClient,
    conteudo: bytes,
    nome: str = "arquivo.ofx",
    owner: str | None = None,
):
    data = {"owner": owner} if owner else None
    return await client.post("/v1/transactions/upload", files={"file": (nome, conteudo)}, data=data)
