# Atas e Checkpoints da Equipe

Registro formal dos alinhamentos, dinâmicas de ideação e deliberações técnicas da equipe do **Trokim** ao longo do Challenge 2.

---

## Índice de Atas de Reunião

| Reunião | Data | Fase CBL | Pauta Central | Documento |
|---|---|---|---|---|
| **Ata 01** | 26/10/2026 | Semana 1 – *Engage* | Alinhamento inicial da Big Idea (Qualidade de Vida), brainstorming, seleção do tema de finanças pessoais e início das 13 Guiding Questions | [Acessar Ata 01](ata01.md) |

---

## Checkpoints Semanais do Projeto

### Checkpoint da Semana 1 — Definições e Escopo (30/10/2026)
- **Status:** <span class="badge-must">Concluído</span>
- **Resultados Consolidados:**
  - Definição do escopo MVP: importação local de extratos OFX e faturas PDF, descartando integrações pesadas de Open Finance ([ADR 0005](../adr/0005-importacao-local-ofx-pdf.md)).
  - Documentação das 13 Guiding Questions com hipóteses e conclusões preliminares.
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
