from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "127.0.0.1"

    DATABASE_URL: str = "sqlite+aiosqlite:///trokim.db"

    # Provedores: "litellm" (qualquer modelo), "ollama" (cliente direto) ou "mock".
    LLM_PROVIDER: str = "litellm"
    # Formato do LiteLLM: "ollama/qwen2.5", "openai/gpt-4o-mini", "anthropic/...".
    LLM_MODEL: str = "ollama/qwen2.5"
    # Vazio usa o padrão do provedor; para Ollama local é http://localhost:11434.
    LLM_API_BASE: str = ""
    LLM_API_KEY: str = ""
    LLM_TIMEOUT: float = 60.0
    # Raciocínio estendido ("thinking") dos modelos locais que o suportam. Desligado por
    # padrão: respostas muito mais rápidas e sem gastar tokens "pensando".
    LLM_THINKING: bool = False
    # Tempo máximo para nomear uma conversa antes de usar o título de reserva.
    LLM_TITLE_TIMEOUT: float = 25.0
    # Modelo leve só para nomear conversas (ex.: "ollama/qwen2.5:1.5b"). Vazio = usa LLM_MODEL.
    LLM_TITLE_MODEL: str = ""
    LLM_TEMPERATURE: float = 0.1

    RAG_SIMILARITY_THRESHOLD: float = 0.15
    RAG_TOP_K: int = 3
    RAG_EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    RAG_VECTOR_DB_PATH: str = "data/vector_store.db"
    RAG_CHUNK_MAX_CHARS: int = Field(default=500, gt=0)
    RAG_CHUNK_OVERLAP_TOKENS: int = Field(default=50, ge=0)
    RAG_HYBRID_ALPHA: float = Field(default=0.3, ge=0, le=1)

    @property
    def vector_db_path(self) -> Path:
        """Caminho do banco vetorial; relativo é resolvido a partir de `api/`, não do cwd."""
        path = Path(self.RAG_VECTOR_DB_PATH)
        return path if path.is_absolute() else API_DIR / path

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
