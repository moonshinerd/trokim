# Planejamento e Roadmap do Projeto

O desenvolvimento do **Trokim** segue a metodologia **Challenge Based Learning (CBL)** ao longo de 7 semanas, alinhado à disciplina TIC-IA 2026.

---

## Roadmap Oficial das 7 Semanas

| Semana | Foco Temático | Entregável Principal | Status no Trokim |
|---|---|---|---|
| **Semana 1** | Problema, stakeholders, riscos e métricas | Definições do projeto, documento norteador e matriz de riscos | <span class="badge-must">Concluído</span> |
| **Semana 2** | Base de conhecimento e recuperação | Primeiro mecanismo RAG e ingestão de fontes oficiais | <span class="badge-p0">Em Execução</span> |
| **Semana 3** | Comparação LLM x RAG | Respostas baseadas em evidências e abstenção fundamentada | Previsto |
| **Semana 4** | Sistema multiagentes | Primeiro sistema multiagentes (orçamento, categorização, auditor) | Previsto |
| **Semana 5** | Multimodalidade | Agentes multimodais (visão computacional para comprovantes/faturas) | Previsto |
| **Semana 6** | Integração completa | Aplicação funcional completa (Flutter + FastAPI + Agentes) | Previsto |
| **Semana 7** | Testes e refinamento | Relatório final, métricas empíricas e apresentação | Previsto |

---

## Detalhamento da Semana 2 (Foco Atual)

A **Semana 2** concentra-se na construção da infraestrutura de conhecimento e recuperação:

1. **Ingestão Curada de Fontes Oficiais:**
   - Caderno de Cidadania Financeira do Banco Central do Brasil ([BCB](https://www.bcb.gov.br)).
   - Guias de Planejamento Financeiro Familiar da Comissão de Valores Mobiliários ([CVM](https://www.gov.br/investidor)).
   - Princípios da *Financial Well-Being Scale* do Consumer Financial Protection Bureau ([CFPB](https://www.consumerfinance.gov)).
2. **Dados Sintéticos para Validação:**
   - Criação de massa sintética de extratos em formato `.ofx` e demonstrativos em `.pdf`.
   - Garantia de conformidade estrita com a LGPD (zero exposição de dados reais de integrantes ou terceiros).
3. **Mecanismo RAG Local:**
   - Fragmentação em chunks com metadados de procedência e citação direta.
   - Mecanismo de busca semântica e abstenção explícita quando a pergunta do usuário não possuir respaldo documental.

---

## Marcos e Critérios de Aceite da Semana 2

- [x] Repositório estruturado com monorepo (`mobile/`, `api/`, `docs/`, `research/`, `deploy/`).
- [x] Documentação viva em MkDocs com ADRs e matriz de rastreabilidade.
- [ ] Ingestão dos documentos regulatórios em formato indexado (`research/knowledge_base/`).
- [ ] Script de benchmark de recuperação com avaliação de revocação (*recall*) e precisão.
- [ ] Endpoint `/v1/chat` integrado ao motor RAG.
