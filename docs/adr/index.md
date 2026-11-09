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

- [0006 — Curadoria rastreável e benchmark](0006-curadoria-benchmark.md)
- [0007 — Banco vetorial local e embeddings densos no RAG](0007-banco-vetorial-embeddings.md)
- [0008 — Material comparativo versionado](0008-material-comparativo-versionado.md)
