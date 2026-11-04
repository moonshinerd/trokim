from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import init_db
from app.routers.v1.budgets import router as budgets_router
from app.routers.v1.chat import router as chat_router
from app.routers.v1.health import router as health_router
from app.routers.v1.transactions import router as transactions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializa banco de dados SQLite local no startup
    await init_db()
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

# Inclusão dos roteadores v1
app.include_router(health_router, prefix="/v1")
app.include_router(transactions_router, prefix="/v1")
app.include_router(chat_router, prefix="/v1")
app.include_router(budgets_router, prefix="/v1")


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
