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

### Checkpoint da Semana 2 — Base de Conhecimento e Primeiro RAG (04/11/2026)
- **Status:** <span class="badge-p0">Em Execução</span>
- **Resultados Consolidados:**
  - Ingestão curada de documentos oficiais: Banco Central do Brasil (BCB), CVM e CFPB.
  - Estruturação do repositório em monorepo com suporte a Zensical/MkDocs.
  - Primeiro motor RAG local implementado com suporte a citação formal e política de abstenção ativa comprovada por benchmark ([ADR 0003](../adr/0003-rag-fontes-oficiais.md)).
