# Backend do Trokim com OCR local (ADR 0021). O app Flutter não entra aqui: ele é instalado no
# aparelho do usuário e fala com esta API.
FROM python:3.12-slim

# Bibliotecas de sistema que o OpenCV (usado pelo RapidOCR) exige.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/srv/.venv/bin:$PATH" \
    FASTEMBED_CACHE_PATH=/opt/fastembed

WORKDIR /srv

# Dependências primeiro (camada em cache), com o extra de OCR e o lock do repositório.
COPY api/pyproject.toml api/uv.lock ./
RUN uv sync --frozen --no-dev --extra ocr

# Baixa o modelo de embeddings na construção: depois disso a API roda sem internet.
RUN python -c "from fastembed import TextEmbedding; \
TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

COPY api/app ./app
COPY api/migrations ./migrations
COPY api/alembic.ini ./alembic.ini
COPY research/knowledge_base /srv/research/knowledge_base

# Descomprime o índice CNPJ versionado (ADR 0020); a API refaz sozinha se o pacote mudar.
RUN python -m app.services.cnpj_index

# Dados do usuário (SQLite e índice vetorial) ficam no volume, nunca na imagem.
RUN useradd --system --create-home trokim && mkdir -p /srv/data && chown -R trokim /srv/data
USER trokim
VOLUME ["/srv/data"]

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/v1/health', timeout=4)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
