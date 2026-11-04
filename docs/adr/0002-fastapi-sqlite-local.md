# 0002 — Backend Local-First em FastAPI com Banco SQLite Embutido

- **Status:** Aceita
- **Data:** 04/11/2026
- **Requisitos / GQs:** RNF01, RNF04, RNF05, GQ03, GQ10

## Contexto
O assistente financeiro lida com dados altamente sensíveis (histórico de transações, faturas de cartão, padrões de consumo). Pela LGPD e pelos princípios de minimização de risco, é desejável que os dados do usuário não precisem trafegar ou ficar armazenados em servidores remotos na nuvem durante os testes e uso inicial. Além disso, a equipe precisa de agilidade operacional, sem depender de containers pesados de banco de dados (como PostgreSQL) para cada teste unitário local.

## Decisão
Implementar a API com **FastAPI (Python 3.12+)** gerenciado por **uv**, adotando o **SQLite** como banco de dados embutido local. A estrutura do código seguirá a separação em camadas limpa (`routers/v1 → services → domain`), garantindo que o domínio do negócio seja independente do driver do banco de dados.

## Alternativas Consideradas
- **FastAPI + PostgreSQL + pgvector (Padrão ContrarIA):** Excelente para grandes volumes de dados concorrentes na web, mas introduz complexidade desnecessária para um app local-first no MVP, exigindo Docker ativo e orquestração contínua.
- **Node.js (Fastify / Express):** Boa integração com JavaScript, mas o ecossistema Python é vastamente superior para processamento de documentos PDF/OFX, bibliotecas de IA e mecanismos RAG.

## Consequências
- **Positivas:**
  - Setup instantâneo: basta clonar o repositório e executar `make setup` e `make api-run`.
  - Privacidade total (zero dados pessoais enviados a bancos externos).
  - Facilidade de transição: como a camada `domain` é desacoplada, uma eventual migração para PostgreSQL com pgvector no futuro exige apenas a troca da porta de repositório.
- **Negativas / Riscos:**
  - Menor suporte a concorrência pesada de múltiplos clientes simultâneos em escrita, o que não é um problema para a arquitetura local de usuário único do Trokim.
