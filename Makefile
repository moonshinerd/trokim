.PHONY: help setup lint format test docs-serve docs-build api-run mobile-run rag-eval synthetic-data research-test

RAG_REPORT ?= artifacts/research/current.json

help:
	@echo "Comandos disponíveis no repositório Trokim:"
	@echo "  make setup          - Cria api/.env e instala dependências locais (uv)"
	@echo "  make lint           - Checagem estática com ruff na api e research"
	@echo "  make format         - Auto-formatação com ruff"
	@echo "  make test           - Executa a bateria de testes automatizados (pytest)"
	@echo "  make docs-serve     - Inicia servidor local de documentação MkDocs (:8001)"
	@echo "  make docs-build     - Compila a documentação estrita (--strict)"
	@echo "  make api-run        - Inicia o servidor backend FastAPI (:8000)"
	@echo "  make mobile-run     - Inicia o aplicativo Flutter no emulador/dispositivo Android"
	@echo "  make rag-eval       - Executa benchmark e avaliação da base RAG (Semana 2)"
	@echo "  make synthetic-data - Gera extratos OFX e faturas sintéticas para testes LGPD"

setup:
	@test -f api/.env || cp api/.env.example api/.env
	cd api && uv sync
	@if command -v flutter >/dev/null 2>&1; then \
		cd mobile && flutter pub get; \
	fi

lint:
	cd api && uv run ruff check . && uv run ruff format --check .
	cd api && uv run ruff check --config pyproject.toml ../research && uv run ruff format --check --config pyproject.toml ../research
	@if command -v flutter >/dev/null 2>&1; then \
		cd mobile && flutter analyze; \
	fi

format:
	cd api && uv run ruff format . && uv run ruff check --fix .
	cd api && uv run ruff format --config pyproject.toml ../research && uv run ruff check --fix --config pyproject.toml ../research

test: research-test
	cd api && uv run pytest

research-test: rag-eval
	cd api && uv run pytest -c pyproject.toml ../research

docs-serve:
	uvx zensical serve

docs-build:
	uvx zensical build --strict

api-run:
	cd api && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

mobile-run:
	cd mobile && flutter run

rag-eval:
	cd api && uv run python ../research/rag_benchmark/eval_rag.py --output "$(abspath $(RAG_REPORT))"

synthetic-data:
	cd api && uv run python ../research/synthetic_data/generate_datasets.py
