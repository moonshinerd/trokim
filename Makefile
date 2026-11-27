.PHONY: help setup lint format test docs-serve docs-build api-run mobile-run rag-eval synthetic-data research-test ingest comparison-validate comparison-eval comparison-run multiagent-run report-charts build cnpj-indice cnpj-atualizar cnpj-download cnpj-index

RAG_REPORT ?= artifacts/research/current.json

help:
	@echo "Comandos disponíveis no repositório Trokim:"
	@echo "  make build               - Prepara a aplicação: dependências e índice CNPJ descomprimido"
	@echo "  make setup               - Cria api/.env e instala dependências locais (uv)"
	@echo "  make lint                - Checagem estática com ruff na api e research"
	@echo "  make format              - Auto-formatação com ruff"
	@echo "  make test                - Executa a bateria de testes automatizados (pytest)"
	@echo "  make docs-serve          - Inicia servidor local de documentação MkDocs (:8001)"
	@echo "  make docs-build          - Compila a documentação estrita (--strict)"
	@echo "  make api-run             - Inicia o servidor backend FastAPI (:8000)"
	@echo "  make mobile-run          - Inicia o aplicativo Flutter no emulador/dispositivo Android"
	@echo "  make rag-eval            - Executa benchmark e avaliação da base RAG (Semana 2)"
	@echo "  make ingest              - Ingere a base de conhecimento no banco vetorial local"
	@echo "  make synthetic-data      - Gera extratos OFX e faturas sintéticas para testes LGPD"
	@echo "  make document-images     - Recria os 40 documentos e o manifesto multimodal (#90)"
	@echo "  make validar-banco ARQUIVO=<arquivo> - Confere um arquivo real de banco e imprime só totais (ADR 0022)"
	@echo "  make document-calibrate RUN=<id> - Calibra e ensaia com OCR real (#88/#90)"
	@echo "  make document-compare RUN=<id> ENGINE=<motor> [MODEL=<modelo>] - Compara leitura (#98)"
	@echo "  make chat-dados-run RUN=<id> MODEL=<modelo> - Avalia chat com contas e dívidas (#98)"
	@echo "  make comparison-validate - Valida integridade do material comparativo (Semana 3)"
	@echo "  make comparison-eval     - Executa o benchmark comparativo das 3 abordagens (Semana 3)"
	@echo "  make comparison-run RUN=<data>-<modelo> MODEL=<modelo litellm> - Execução completa e registrada"
	@echo "                             (4 abordagens nos 30 casos + 20 cenários; recusa RUN já usado)"
	@echo "  make multiagent-run RUN=<data>-<modelo> MODEL=<modelo> - Só os 20 cenários multiagente"
	@echo "  make report-charts       - Gera os gráficos versionados do benchmark para o MkDocs"
	@echo "  make cnpj-indice         - Descomprime o índice CNPJ versionado em api/data/cnpj (rápido)"
	@echo "  make cnpj-atualizar      - Baixa o mês mais recente da Receita (~5 GB), refaz o índice e o"
	@echo "                             dicionário e apaga o download (pede confirmação; CONFIRMAR=sim,"
	@echo "                             MES=AAAA-MM, MANTER_DOWNLOAD=1, FORCAR=1, CNPJ_BASE=<pasta>)"
	@echo "  make cnpj-download / cnpj-index MES=AAAA-MM - Passos avulsos do cnpj-atualizar"

setup:
	@test -f api/.env || cp api/.env.example api/.env
	cd api && uv sync
	@if command -v flutter >/dev/null 2>&1; then \
		cd mobile && flutter pub get; \
	fi
	@$(MAKE) -s cnpj-indice

# Prepara tudo para rodar: dependências e o índice CNPJ descomprimido do pacote versionado.
build: setup

cnpj-indice:
	cd api && uv run python -m app.services.cnpj_index

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

research-test: rag-eval comparison-validate
	cd api && uv run pytest -c pyproject.toml ../research

comparison-validate:
	cd api && uv run python ../research/rag_benchmark/comparison.py

comparison-eval:
	cd api && uv run python ../research/rag_benchmark/run_comparison.py

docs-serve:
	uvx zensical serve

docs-build:
	uvx zensical build --strict

api-run: cnpj-indice
	cd api && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

mobile-run:
	cd mobile && flutter run

rag-eval:
	cd api && uv run python ../research/rag_benchmark/eval_rag.py --output "$(abspath $(RAG_REPORT))"

ingest:
	cd api && uv run python -m app.services.ingestion_service

synthetic-data:
	cd api && uv run python ../research/synthetic_data/generate_datasets.py

.PHONY: validar-banco document-images document-calibrate document-compare chat-dados-run
validar-banco:
	@test -n "$(ARQUIVO)" || (echo "uso: make validar-banco ARQUIVO=/caminho/do/arquivo"; exit 2)
	cd api && uv run python -m scripts.validar_banco "$(abspath $(ARQUIVO))"

document-images:
	cd api && uv run python ../research/synthetic_data/generate_document_images.py

document-compare:
	@test -n "$(RUN)" -a -n "$(ENGINE)" || { echo "Uso: make document-compare RUN=<id> ENGINE=ocr|ocr+vlm-local|ocr+vlm-remoto [MODEL=<modelo>]"; exit 1; }
	cd api && uv run --extra documents --extra ocr python ../research/rag_benchmark/compare_document_engines.py \
		--run "$(RUN)" --engine "$(ENGINE)" $(if $(MODEL),--model "$(MODEL)") $(if $(PRICE),--price $(PRICE))

chat-dados-run:
	@test -n "$(RUN)" -a -n "$(MODEL)" || { echo "Uso: make chat-dados-run RUN=<id> MODEL=<modelo>"; exit 1; }
	cd api && uv run python ../research/rag_benchmark/run_chat_dados.py --run "$(RUN)" --model "$(MODEL)"

document-calibrate:
	@test -n "$(RUN)" || { echo "Uso: make document-calibrate RUN=2026-11-23-rapidocr-v1"; exit 1; }
	cd api && uv run --extra documents --extra ocr python ../research/rag_benchmark/calibrate_documents.py \
		--ocr --output "../research/rag_benchmark/results/documents/$(RUN)"

# Execução completa e registrada do benchmark (#60): as quatro abordagens nos 30 casos e os 20
# cenários multiagente, em results/comparison/<RUN>/ e results/multiagent/<RUN>/, com run.json e
# formulários de auditoria pendente. Recusa RUN já usado. Depois: `make report-charts`.
comparison-run:
	@test -n "$(RUN)" -a -n "$(MODEL)" || { echo "Uso: make comparison-run RUN=2026-11-20-qwen2.5-7b MODEL=ollama/qwen2.5:7b [NOTAS='...']"; exit 1; }
	cd api && uv run python ../research/rag_benchmark/run_comparison.py --provider litellm --model "$(MODEL)" \
		--temperature 0.1 --multiagent --run-id "$(RUN)" --notas "$(NOTAS)"
	$(MAKE) -s multiagent-run RUN="$(RUN)" MODEL="$(MODEL)"

# Só os 20 cenários multiagente (o resumo entra no run.json da mesma execução, se existir).
multiagent-run:
	@test -n "$(RUN)" -a -n "$(MODEL)" || { echo "Uso: make multiagent-run RUN=2026-11-18-qwen2.5-1.5b MODEL=ollama/qwen2.5:1.5b"; exit 1; }
	cd api && uv run python ../research/rag_benchmark/run_multiagent.py --model "$(MODEL)" --temperature 0.1 \
		--run-id "$(RUN)"

# Gráficos dos docs: lidos de run.json e dos resultados; matplotlib só é trazido por este comando.
report-charts:
	cd api && uv run python ../research/rag_benchmark/document_charts.py
	uv run --with matplotlib python research/rag_benchmark/make_report_charts.py

# Categorização por atividade (ADR 0020): dados abertos do CNPJ, baixados uma vez, fora do git.
MES ?=
CNPJ_BASE ?= $(HOME)/dados/receita-cnpj
CNPJ_ORIGEM ?= $(CNPJ_BASE)/$(MES)

cnpj-atualizar:
	cd api && uv run python ../research/cnpj/atualizar.py --base "$(CNPJ_BASE)" \
		$(if $(MES),--mes $(MES)) $(if $(filter sim SIM,$(CONFIRMAR)),--sim) \
		$(if $(MANTER_DOWNLOAD),--manter-download) $(if $(FORCAR),--forcar)

cnpj-download:
	@test -n "$(MES)" || { echo "Uso: make cnpj-download MES=2026-11"; exit 1; }
	research/cnpj/baixar.sh $(MES) "$(CNPJ_ORIGEM)"

cnpj-index:
	@test -n "$(MES)" || { echo "Uso: make cnpj-index MES=2026-11"; exit 1; }
	cd api && uv run python ../research/cnpj/gerar_indice_cnpj.py --origem "$(CNPJ_ORIGEM)"
