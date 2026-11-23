from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import init_db
from app.routers.v1.agents import router as agents_router
from app.routers.v1.backup import router as backup_router
from app.routers.v1.banks import router as banks_router
from app.routers.v1.budgets import router as budgets_router
from app.routers.v1.chat import router as chat_router
from app.routers.v1.health import router as health_router
from app.routers.v1.library import router as library_router
from app.routers.v1.library_snapshot import router as library_snapshot_router
from app.routers.v1.transactions import router as transactions_router
from app.services import library_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializa banco de dados SQLite local no startup
    await init_db()
    # Restaura a biblioteca do usuário gravada na última execução (ADR 0024).
    await run_in_threadpool(library_store.restore)
    yield


app = FastAPI(
    title="Trokim API",
    description=(
        "Backend local-first para assistente financeiro pessoal com RAG "
        "e parsing de extratos (OFX/PDF)."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS para desenvolvimento com o app Flutter e navegadores
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rotas que alteram a biblioteca do usuário: depois delas, a biblioteca é gravada (ADR 0024).
_MUTATING_PREFIXES = (
    "/v1/transactions",
    "/v1/accounts",
    "/v1/statements",
    "/v1/transfers",
    "/v1/backup",
    "/v1/library",
)


class PersistLibraryMiddleware:
    """Grava a biblioteca depois das rotas que a alteram (ADR 0024).

    É um middleware ASGI puro, e não ``BaseHTTPMiddleware``, para não interferir na detecção de
    desconexão do cliente usada ao cancelar a geração (``run_while_connected``).
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope["method"] not in {"POST", "PATCH", "PUT", "DELETE"}:
            await self.app(scope, receive, send)
            return
        if not scope["path"].startswith(_MUTATING_PREFIXES):
            await self.app(scope, receive, send)
            return
        status = 500

        async def send_wrapper(message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)
        if status < 400:
            await run_in_threadpool(library_store.persist)


app.add_middleware(PersistLibraryMiddleware)


# Inclusão dos roteadores v1
app.include_router(health_router, prefix="/v1")
app.include_router(transactions_router, prefix="/v1")
app.include_router(library_router, prefix="/v1")
app.include_router(library_snapshot_router, prefix="/v1")
app.include_router(chat_router, prefix="/v1")
app.include_router(budgets_router, prefix="/v1")
app.include_router(agents_router, prefix="/v1")
app.include_router(backup_router, prefix="/v1")
app.include_router(banks_router, prefix="/v1")


@app.get("/")
async def root():
    return {
        "project": "Trokim",
        "description": (
            "Assistente financeiro pessoal open-source com RAG e foco em qualidade de vida."
        ),
        "documentation": "/docs",
        "health": "/v1/health",
    }
