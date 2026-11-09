# Arquitetura do Sistema

A arquitetura do **Trokim** foi concebida para atender aos requisitos de alta performance de recuperação semântica, estrita observância à LGPD (*privacy by design / local-first*) e integridade nos cálculos orçamentários.

---

## Decisões Estruturais Principais

1. **Camada Mobile (Android / Flutter):**
   - Desenvolvida em Dart/Flutter, garantindo tipagem estrita, modularidade por funcionalidades (*feature-first*) e compilação nativa para Android.
   - O aplicativo atua como o cliente primário, fornecendo telas de dashboard, assistente conversacional, gerenciador de lançamentos e importador de arquivos OFX e faturas PDF.
2. **Camada Backend (FastAPI / Python 3.12+):**
   - Construída com FastAPI pela alta performance assíncrona e tipagem robusta com Pydantic v2.
   - Gerenciamento de dependências ultra-rápido com `uv`.
   - Banco de dados embutido **SQLite** garantindo funcionamento 100% *local-first* sem necessidade de servidores externos.
3. **Mecanismo RAG Híbrido e Banco Vetorial (Semana 2):**
   - Embeddings multilíngues gerados localmente pelo modelo `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dimensões) via **FastEmbed**.
   - Persistência e indexação vetorial nativa em SQLite com a extensão **sqlite-vec** (tabela virtual `vec0`).
   - Busca híbrida combinando proximidade de cosseno denso com TF-IDF esparso (palavras e n-grams de caracteres), com calibração balanceada ($\alpha = 0,3$).
   - Política ativa de **abstenção ética**: se o score estiver abaixo do limiar ou a consulta abordar temas fora do escopo institucional (apostas, criptoativos ou recomendações especulativas), o agente se abstém.
4. **Cálculo Determinístico:**
   - A LLM nunca calcula saldos, médias ou limites. Um serviço matemático estrito (`calculation_service.py`) computa os números exatos e os injeta contextualmente.
5. **Camada de Síntese Generativa Local (Semana 3):**
   - Port abstrato `LLMProvider` desacoplando as regras de negócio dos provedores de inferência.
   - Provedor primário local-first `OllamaProvider` executando **Qwen 2.5** (`qwen2.5`) localmente sem envio de dados a nuvens terceiras.
   - Provedor simulado determinístico `MockLLMProvider` para execução reprodutível de testes e CI.
   - Orquestrador `GenerationService` suportando três modos de síntese (`grounded`, `pure`, `naive`), prompts versionados e corte estrito de alucinações via abstenção ética determinística.

---

## Camadas do Backend (`api/`)

O backend adota uma arquitetura em camadas limpa e desacoplada:

```text
routers/ (HTTP fino, esquemas Pydantic: /transactions, /chat/ask, /chat/generate)
   │
   ▼
services/ (Regras de negócio: CalculationService, RAGService, GenerationService)
   │
   ▼
domain/   (Entidades de negócio puras: Transaction, Budget, Evidence)
   ▲
   │
clients/  (Adaptadores de persistência e LLM: SQLiteVectorStore, FastEmbed, OllamaProvider, MockLLMProvider)
```

Essa estrutura garante que a evolução do sistema nas semanas subsequentes (Semanas 3 a 5: Comparação LLM x RAG, Multiagentes e Multimodalidade) ocorra sem acoplamento indevido.
