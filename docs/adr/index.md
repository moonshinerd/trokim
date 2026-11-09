# Registro de Decisões de Arquitetura (ADRs)

Este repositório registra formalmente todas as decisões de arquitetura e tecnologia que orientam o desenvolvimento do **Trokim**, garantindo rastreabilidade histórica em relação aos Requisitos e às Perguntas Norteadoras (GQs).

---

## Índice Consolidado de Decisões

| ADR | Título | Status | Data | Vínculo (RF / RNF / GQ) |
|:---:|---|:---:|:---:|---|
| [**0001**](0001-flutter-android.md) | Adoção do Flutter para Desenvolvimento do App Android | <span class="badge-must">Aceita</span> | 04/11/2026 | RF07, RNF03, GQ07 |
| [**0002**](0002-fastapi-sqlite-local.md) | Backend Local-First em FastAPI com Banco SQLite Embutido | <span class="badge-must">Aceita</span> | 04/11/2026 | RNF01, RNF05, GQ03 |
| [**0003**](0003-rag-fontes-oficiais.md) | Mecanismo RAG Fundamentado em Órgãos Oficiais (BCB, CVM, CFPB) | <span class="badge-must">Aceita</span> | 04/11/2026 | RF05, RF06, RF10, GQ05 |
| [**0004**](0004-calculos-deterministicos.md) | Separação entre Cálculos Determinísticos e Síntese de Linguagem | <span class="badge-must">Aceita</span> | 04/11/2026 | RF03, RF04, RNF02, GQ04 |
| [**0005**](0005-importacao-local-ofx-pdf.md) | Importação de Extratos Locais (OFX/PDF) em vez de Open Finance no MVP | <span class="badge-must">Aceita</span> | 04/11/2026 | RF01, RF02, RNF01, GQ02 |
| [**0006**](0006-curadoria-benchmark.md) | Curadoria Rastreável de 20 Documentos e Benchmark Empírico | <span class="badge-must">Aceita</span> | 06/11/2026 | RF05, RF06, RNF06, GQ05, GQ08 |
| [**0007**](0007-banco-vetorial-embeddings.md) | Banco Vetorial Local (SQLite-Vec) e Embeddings Densos Híbridos | <span class="badge-must">Aceita</span> | 07/11/2026 | RF05, RF06, RF10, RNF04, GQ05, GQ10 |

---

## Síntese das Decisões por Fase do Projeto

### Concepção e Fundamentos (Semana 1)
- **ADR 0001 (Flutter Android):** Escolha do Flutter para interface mobile por prover componentes nativos Material 3, modularidade vertical (*feature-first*) e compilação direta sem pontes web lentas.
- **ADR 0002 (FastAPI + SQLite Local):** Adoção de arquitetura estritamente *local-first*, eliminando servidores de banco de dados e assegurando soberania de dados do usuário (LGPD).
- **ADR 0003 (RAG em Fontes Oficiais):** Exigência de que toda resposta pedagógica do assistente derive com exclusividade de cadernos oficiais do BCB, CVM e CFPB, com abstenção ativa em tópicos especulativos.
- **ADR 0004 (Cálculos Determinísticos):** Proibição da LLM de efetuar operações aritméticas de saldos ou orçamentos, delegando o cálculo a funções puras em Python.
- **ADR 0005 (Extratos OFX e PDF):** Foco no processamento local de arquivos bancários fornecidos pelo usuário, descartando integrações complexas e invasivas de Open Finance.

### Base de Conhecimento e Recuperação RAG (Semana 2)
- **ADR 0006 (Curadoria Rastreável e Benchmark):** Estruturação do catálogo de 20 fontes com hashes SHA-256 de proveniência, gabarito de 61 consultas e metas mínimas (Recall@3 $\ge 90\%$, Abstenção $= 100\%$).
- **ADR 0007 (Banco Vetorial e Embeddings Densos):** Implementação de persistência vetorial nativa em SQLite (`sqlite-vec` / `vec0`) e embeddings multilíngues via FastEmbed (`MiniLM-L12-v2` 384d), com busca híbrida densa/léxica calibrada em $\alpha = 0,3$.
