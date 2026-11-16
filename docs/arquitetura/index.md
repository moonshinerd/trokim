# Arquitetura do Sistema

A arquitetura do **Trokim** foi concebida para atender aos requisitos de alta performance de recuperação semântica, estrita observância à LGPD (*privacy by design / local-first*) e integridade nos cálculos orçamentários.

---

## Decisões Estruturais Principais

1. **Camada Mobile (Android / Flutter):**
   - Desenvolvida em Dart/Flutter, garantindo tipagem estrita, modularidade por funcionalidades (*feature-first*) e compilação nativa para Android.
   - O aplicativo atua como o cliente primário, fornecendo telas de dashboard, assistente conversacional, gerenciador de lançamentos e importador de arquivos OFX e faturas PDF.
   - A interface segue um design system próprio (paleta Champagne, Tidewater e Fortuna Gold, [ADR 0011](../adr/0011-identidade-visual-e-tema-do-sistema.md)) com tema claro/escuro pelo sistema, transições suaves que respeitam "reduzir movimento" e uma aba de **Ajustes** com preferências salvas só no aparelho ([ADR 0013](../adr/0013-preferencias-locais-e-aba-de-ajustes.md)). O mascote (onça-pintada) e a moeda 3D da abertura vêm de arte livre e trocável ([ADR 0012](../adr/0012-mascote-onca-e-arte-de-marca-livre.md)).
   - Resumo e Extratos exibem o que a API calculou e importam OFX e PDF pelo seletor de arquivos do sistema ([ADR 0015](../adr/0015-dados-reais-importacao-e-endereco-da-api.md)); o chat guarda o histórico no aparelho, com título gerado pelo LLM local.
2. **Camada Backend (FastAPI / Python 3.12+):**
   - Construída com FastAPI pela alta performance assíncrona e tipagem robusta com Pydantic v2.
   - Gerenciamento de dependências ultra-rápido com `uv`.
   - Banco de dados embutido **SQLite** garantindo funcionamento 100% *local-first* sem necessidade de servidores externos.
3. **Mecanismo RAG Híbrido e Banco Vetorial (Semana 2):**
   - Embeddings multilíngues gerados localmente pelo modelo `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dimensões) via **FastEmbed**.
   - Persistência e indexação vetorial nativa em SQLite com a extensão **sqlite-vec** (tabela virtual `vec0`).
   - Busca híbrida combinando proximidade de cosseno denso com TF-IDF esparso (palavras e n-grams de caracteres), com calibração balanceada (α = 0,3).
   - Política ativa de **abstenção ética**: se o score estiver abaixo do limiar ou a consulta abordar temas fora do escopo institucional (apostas, criptoativos ou recomendações especulativas), o agente se abstém.
4. **Cálculo Determinístico:**
   - A LLM nunca calcula saldos, médias ou limites. Um serviço matemático estrito (`calculation_service.py`) computa os números exatos e os injeta contextualmente.
5. **Camada de Síntese Generativa Local (Semana 3, [ADR 0009](../adr/0009-sintese-generativa-local.md)):**
   - Port abstrato `LLMProvider` desacoplando as regras de negócio dos provedores de inferência.
   - `LiteLLMProvider` (padrão): qualquer modelo definido por configuração (`LLM_MODEL`, por exemplo `ollama/qwen2.5:1.5b`). Modelos locais não enviam dados a terceiros; modelos de nuvem são uma escolha explícita.
   - `OllamaProvider` (cliente direto) e `MockLLMProvider` (determinístico, para testes e CI).
   - `GenerationService` com três modos (`grounded`, `naive`, `pure`), prompts versionados e abstenção determinística (fora de escopo ou sem evidência) antes de chamar o modelo; `TitleService` dá título às conversas (`/v1/chat/title`, [ADR 0014](../adr/0014-historico-de-conversas-e-titulos.md)).
6. **Sistema Multiagente Determinístico e Auditável (Semana 4, [ADR 0016](../adr/0016-arquitetura-multiagente.md)):**
   - Orquestrador determinístico coordenando quatro agentes especializados: `ResearchAgent` (recuperação de evidências e verificação de escopo), `AnalysisAgent` (cálculos matemáticos determinísticos sem LLM), `CommunicationAgent` (redação pedagógica ancorada em fontes oficiais) e `ValidationAgent` (auditoria defensiva factual contra alucinações).
   - Exposição via endpoint HTTP `POST /v1/agents/ask` devolvendo `MultiAgentResponse` com a trilha de auditoria (`steps`) detalhando o papel e tempo de execução de cada agente.

---

## Camadas do Backend (`api/`)

O backend adota uma arquitetura em camadas limpa e desacoplada:

```text
routers/ (HTTP fino, esquemas Pydantic: /transactions, /chat/ask, /chat/generate, /chat/title, /budgets, /agents/ask)
   │
   ▼
services/ (Regras de negócio: CalculationService, ParserService, RAGService, GenerationService, TitleService, Orchestrator e agentes)
   │
   ▼
domain/   (Entidades de negócio puras: Transaction, Budget, EvidenceChunk, MultiAgentResponse)
   ▲
   │
clients/  (Adaptadores de persistência e LLM: SQLiteVectorStore, FastEmbed, LiteLLMProvider, OllamaProvider, MockLLMProvider)
```

Essa estrutura garante que a evolução do sistema nas semanas seguintes (Semana 4: multiagentes; Semana 5: multimodalidade; Semana 6: integração) ocorra sem acoplamento indevido.
