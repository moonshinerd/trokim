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
| [**0015**](0015-dados-reais-importacao-e-endereco-da-api.md) | Resumo e Extratos com Dados Reais da API, Importação pelo App e Endereço da API Editável | <span class="badge-must">Aceita</span> | 16/11/2026 | RF01, RF02, RF07, RF15, RNF03, RNF10, GQ01, GQ02, GQ03, GQ07 |
| [**0016**](0016-arquitetura-multiagente.md) | Arquitetura Multiagente: Research, Analysis, Communication e Validation | <span class="badge-must">Aceita</span> | 18/11/2026 | RF18, RF19, RF20, RF21, GQ01, GQ05, GQ10, GQ11 |
| [**0017**](0017-perfis-de-banco-e-natureza-do-lancamento.md) | Perfis de Banco, Natureza do Lançamento e Privacidade dos Pix | <span class="badge-must">Aceita</span> | 18/11/2026 | RF01, RF02, RF09, GQ02, GQ03 |
| [**0018**](0018-contas-periodos-transferencias-e-visoes.md) | Contas, Períodos, Transferências entre Contas Próprias e Visões de Caixa e Competência | <span class="badge-must">Aceita</span> | 18/11/2026 | RF01, RF02, RF09, RF22 a RF26, GQ02, GQ03, GQ07, GQ09, GQ13 |
| [**0019**](0019-orm-e-migracoes-numeradas.md) | ORM (SQLAlchemy) e Migrações Numeradas (Alembic) nos Bancos SQLite | <span class="badge-must">Aceita</span> | 18/11/2026 | RF12, RNF01, RNF05, RNF07, GQ03, GQ06 |
| [**0020**](0020-categorizacao-por-cnae.md) | Categorização por Atividade Econômica (CNAE) com Dados Abertos do CNPJ | <span class="badge-must">Aceita</span> | 18/11/2026 | RF09, RNF01, GQ03, GQ07, GQ11 |
| [**0021**](0021-visao-e-ocr-modulares.md) | Leitura de Imagem Modular: Portas de OCR e de Visão e Revisão Humana de Documentos | <span class="badge-must">Aceita</span> | 23/11/2026 | RF27, RF28, RNF01, RNF10, RNF12, GQ01, GQ02, GQ03 |
| [**0022**](0022-registro-de-perfis-e-niveis-de-suporte.md) | Registro de Perfis de Banco, Níveis de Suporte e Tutoriais Guiados | <span class="badge-must">Aceita</span> | 23/11/2026 | RF29, RF15; GQ01, GQ03 |
| [**0023**](0023-contexto-do-usuario-no-chat.md) | Contexto do usuário no chat | <span class="badge-must">Aceita</span> | 25/11/2026 | RF18, RF19, RF20, RF30; GQ05, GQ07, GQ09 |
| [**0024**](0024-persistencia-local-e-backup-criptografado.md) | Persistência Local da Biblioteca e Backup Criptografado | <span class="badge-must">Aceita</span> | 23/11/2026 | RF31, RF32, RNF01, RNF05, GQ03, GQ06 |
| [**0025**](0025-armazenamento-no-aparelho-e-api-sem-estado.md) | Armazenamento no Aparelho e API sem Estado | <span class="badge-must">Aceita</span> | 23/11/2026 | RF31, RF32, RNF01, RNF05, GQ03, GQ06 |
| [**0026**](0026-confirmacao-e-consulta-de-documentos.md) | Confirmação Integral e Consulta Local de Documentos | <span class="badge-must">Aceita</span> | 25/11/2026 | RF27, RF28, RF31, RNF12, GQ02, GQ03, GQ05 |

- [0006 — Curadoria rastreável e benchmark](0006-curadoria-benchmark.md)
- [0007 — Banco vetorial local e embeddings densos no RAG](0007-banco-vetorial-embeddings.md)
- [0008 — Material comparativo versionado](0008-material-comparativo-versionado.md)
- [0009 — Síntese generativa local e camada LiteLLM](0009-sintese-generativa-local.md)
- [0010 — CI em runners hospedados](0010-ci-em-runners-hospedados.md)
- [0011 — Identidade visual e tema do sistema](0011-identidade-visual-e-tema-do-sistema.md)
- [0012 — Mascote onça-pintada e arte livre](0012-mascote-onca-e-arte-de-marca-livre.md)
- [0013 — Preferências locais e aba de Ajustes](0013-preferencias-locais-e-aba-de-ajustes.md)
- [0014 — Histórico de conversas e títulos](0014-historico-de-conversas-e-titulos.md)
- [0015 — Dados reais, importação e endereço da API](0015-dados-reais-importacao-e-endereco-da-api.md)
- [0016 — Arquitetura multiagente](0016-arquitetura-multiagente.md)
- [0017 — Perfis de banco e natureza do lançamento](0017-perfis-de-banco-e-natureza-do-lancamento.md)
- [0018 — Contas, períodos, transferências e visões](0018-contas-periodos-transferencias-e-visoes.md)
- [0019 — ORM e migrações numeradas](0019-orm-e-migracoes-numeradas.md)
- [0020 — Categorização por CNAE com dados abertos do CNPJ](0020-categorizacao-por-cnae.md)
- [0021 — Leitura de imagem modular (OCR e visão) e revisão humana de documentos](0021-visao-e-ocr-modulares.md)
- [0022 — Registro de perfis de banco, níveis de suporte e tutoriais guiados](0022-registro-de-perfis-e-niveis-de-suporte.md)
- [0023 — Contexto do usuário no chat](0023-contexto-do-usuario-no-chat.md)
- [0024 — Persistência local da biblioteca e backup criptografado](0024-persistencia-local-e-backup-criptografado.md)
- [0025 — Armazenamento no aparelho e API sem estado](0025-armazenamento-no-aparelho-e-api-sem-estado.md)
- [0026 — Confirmação integral e consulta local de documentos](0026-confirmacao-e-consulta-de-documentos.md)
