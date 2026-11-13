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
| [**0008**](0008-material-comparativo-versionado.md) | Material Comparativo Versionado e Separado do Benchmark Extrativo | <span class="badge-must">Aceita</span> | 09/11/2026 | RF03, RF05, RF06, RF10, RNF02, RNF06, GQ04, GQ05, GQ08, GQ10, GQ11 |
| [**0009**](0009-sintese-generativa-local.md) | Síntese Generativa Local com Camada LiteLLM e Limites de Fundamentação | <span class="badge-must">Aceita</span> | 13/11/2026 | RF03, RF05, RF06, RF10, RF17, RNF01, RNF02, GQ04, GQ05, GQ10, GQ11 |
| [**0010**](0010-ci-em-runners-hospedados.md) | CI em Runners Hospedados do GitHub Actions | <span class="badge-must">Aceita</span> | 13/11/2026 | RNF06, RNF08, GQ08 |
| [**0011**](0011-identidade-visual-e-tema-do-sistema.md) | Identidade Visual, Design System e Tema Claro/Escuro pelo Sistema | <span class="badge-must">Aceita</span> | 13/11/2026 | RNF03, RNF10, GQ01, GQ07 |
| [**0012**](0012-mascote-onca-e-arte-de-marca-livre.md) | Mascote Onça-Pintada e Arte de Marca com Licença Livre | <span class="badge-must">Aceita</span> | 13/11/2026 | RNF11, GQ01, GQ03 |
| [**0013**](0013-preferencias-locais-e-aba-de-ajustes.md) | Preferências Salvas Localmente e Aba de Ajustes | <span class="badge-must">Aceita</span> | 13/11/2026 | RF15, RNF01, RNF10, GQ01, GQ03 |
| [**0014**](0014-historico-de-conversas-e-titulos.md) | Histórico de Conversas Local e Títulos Gerados pelo LLM | <span class="badge-must">Aceita</span> | 13/11/2026 | RF16, RNF01, GQ01, GQ03, GQ05 |

- [0006 — Curadoria rastreável e benchmark](0006-curadoria-benchmark.md)
- [0007 — Banco vetorial local e embeddings densos no RAG](0007-banco-vetorial-embeddings.md)
- [0008 — Material comparativo versionado](0008-material-comparativo-versionado.md)
- [0009 — Síntese generativa local e camada LiteLLM](0009-sintese-generativa-local.md)
- [0010 — CI em runners hospedados](0010-ci-em-runners-hospedados.md)
- [0011 — Identidade visual e tema do sistema](0011-identidade-visual-e-tema-do-sistema.md)
- [0012 — Mascote onça-pintada e arte livre](0012-mascote-onca-e-arte-de-marca-livre.md)
- [0013 — Preferências locais e aba de Ajustes](0013-preferencias-locais-e-aba-de-ajustes.md)
- [0014 — Histórico de conversas e títulos](0014-historico-de-conversas-e-titulos.md)
