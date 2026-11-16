# Atas e Checkpoints da Equipe

Registro formal dos alinhamentos, dinâmicas de ideação e deliberações técnicas da equipe do **Trokim** ao longo do Challenge 2.

---

## Índice de Atas de Reunião

| Reunião | Data | Fase CBL | Pauta Central | Documento |
|---|---|---|---|---|
| **Ata 01** | 26/10/2026 | Semana 1 – *Engage* | Alinhamento inicial da Big Idea (Qualidade de Vida), brainstorming, seleção do tema de finanças pessoais e início das 10 Guiding Questions | [Acessar Ata 01](ata01.md) |
| **Ata 02** | 06/11/2026 | Semana 2 – *Investigate & Act* | Consolidação da Base de Conhecimento (20 docs), motor vetorial SQLite-Vec + FastEmbed, benchmark RAG (98,78% recall, 100% abstenção) e chat Flutter | [Acessar Ata 02](ata02.md) |
| **Ata 03** | 09/11/2026 | Semana 3 – *Investigate & Act* | Planejamento da Semana 3 (Comparação LLM x RAG), distribuição de tarefas não-bloqueantes, Milestone 2 (13/11) e métricas de alucinação | [Acessar Ata 03](ata03.md) |

---

## Checkpoints Semanais do Projeto

### Checkpoint da Semana 1 — Definições e Escopo (30/10/2026)
- **Status:** <span class="badge-must">Concluído</span>
- **Resultados Consolidados:**
  - Definição do escopo MVP: importação local de extratos OFX e faturas PDF, descartando integrações pesadas de Open Finance ([ADR 0005](../adr/0005-importacao-local-ofx-pdf.md)).
  - Documentação das 10 Guiding Questions com hipóteses e conclusões preliminares.
  - Matriz de riscos e mitigação em conformidade com a LGPD e cálculos determinísticos ([ADR 0004](../adr/0004-calculos-deterministicos.md)).

---

### Checkpoint da Semana 2 — Base de Conhecimento e Primeiro RAG (06/11/2026)
- **Status:** <span class="badge-must">Concluído</span>
- **Resultados Consolidados:**
  - Curadoria e catalogação de 20 documentos oficiais de órgãos reguladores (BCB, CVM, CFPB, ANPD) com metadados e hashes SHA-256 ([ADR 0006](../adr/0006-curadoria-benchmark.md)).
  - Implementação do banco vetorial local (SQLite + `sqlite-vec`), chunking semântico e embeddings multilíngues via FastEmbed ([ADR 0007](../adr/0007-banco-vetorial-embeddings.md)).
  - Benchmark automatizado com 61 consultas: 98,78% de recall@3 e 100% de abstenção ativa em perguntas fora de escopo.
  - Endpoint `POST /v1/chat/ask` integrado à interface do aplicativo Flutter com exibição de cartões de fontes e tratamento de falhas.
  - Geração de extrato OFX e fatura PDF sintéticos para validação local em conformidade estrita com a LGPD.

---

### Checkpoint da Semana 3 — Comparação LLM x RAG (16/11/2026)
- **Status:** <span class="badge-must">Concluído</span> (com pendências assumidas, listadas abaixo)
- **Resultados Consolidados:**
  - Gabarito de 30 casos e três prompts versionados ([#20](https://github.com/moonshinerd/trokim/issues/20), [ADR 0008](../adr/0008-material-comparativo-versionado.md)); framework de métricas de fidelidade factual, F1 de tokens e cobertura de conceitos ([#21](https://github.com/moonshinerd/trokim/issues/21)).
  - Cartões de evidência e auditoria no Flutter ([#22](https://github.com/moonshinerd/trokim/issues/22)); camada de síntese com `LLMProvider`, LiteLLM, Ollama e mock, e endpoints `/v1/chat/generate` e `/v1/chat/title` ([#23](https://github.com/moonshinerd/trokim/issues/23), [ADR 0009](../adr/0009-sintese-generativa-local.md)).
  - Benchmark comparativo das três abordagens ([#24](https://github.com/moonshinerd/trokim/issues/24)) e integração do chat generativo no app ([#25](https://github.com/moonshinerd/trokim/issues/25)).
  - Relatório comparativo, histórico versionado de resultados com gráficos e documentação ([#26](https://github.com/moonshinerd/trokim/issues/26)); histórico de conversas ([#44](https://github.com/moonshinerd/trokim/issues/44)) e dados reais no app ([#45](https://github.com/moonshinerd/trokim/issues/45)).
  - Resultado central: a fundamentação em evidências reduziu as alucinações confirmadas de 30,0% (piso) na LLM pura para 13,3% (RAG ingênuo) e 6,7% (Trokim estruturado); uma segunda execução mudou os números, então o ranking entre RAG ingênuo e Trokim não se sustenta ([Histórico de Resultados](../pesquisa/resultados.md)).
- **Pendências assumidas:** homologação do chat generativo em aparelho Android físico; revisão humana cega e repetição com modelos maiores; persistência dos lançamentos em SQLite. Não houve reunião de validação, então não há Ata 04.
