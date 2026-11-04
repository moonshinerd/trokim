FROM python:3.12-slim

# Instala ferramentas básicas
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instala uv para gerenciamento ultra-rápido de dependências
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /srv

# Copia arquivos de configuração de dependências
COPY api/pyproject.toml ./

# Sincroniza ambiente virtual congelado
RUN uv sync --no-dev

# Copia código da aplicação e base de conhecimento
COPY api/app ./app
COPY research/knowledge_base /srv/research/knowledge_base

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
