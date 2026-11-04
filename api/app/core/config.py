from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "127.0.0.1"

    DATABASE_URL: str = "sqlite+aiosqlite:///trokim.db"

    LLM_MODEL: str = "ollama/llama3.2"
    LLM_API_BASE: str = "http://localhost:11434"
    LLM_API_KEY: str = ""

    RAG_SIMILARITY_THRESHOLD: float = 0.15
    RAG_TOP_K: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
