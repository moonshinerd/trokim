# 0003 — Mecanismo RAG Fundamentado em Órgãos Oficiais (BCB, CVM, CFPB)

- **Status:** Aceita
- **Data:** 04/11/2026
- **Requisitos / GQs:** RF05, RF06, RF10, GQ05, GQ08

## Contexto
Assistentes financeiros baseados em LLMs convencionais correm alto risco de emitir conselhos não fundamentados, alucinar sobre regras tributárias ou fazer recomendações de investimentos arriscados, contrariando as boas práticas alertadas pelo CFPB no relatório *Chatbots in Consumer Finance*. O projeto exige que todas as informações pedagógicas fornecidas ao usuário sejam verificáveis e lastreadas em evidências regulatórias reconhecidas.

## Decisão
Implementar um mecanismo de **Retrieval-Augmented Generation (RAG)** restrito aos manuais e publicações oficiais de três entidades regulatórias de referência:
1. **Banco Central do Brasil (BCB)** — Caderno de Cidadania Financeira;
2. **Comissão de Valores Mobiliários (CVM)** — Guias de Planejamento Financeiro Familiar;
3. **Consumer Financial Protection Bureau (CFPB)** — Escala de Bem-Estar Financeiro e princípios de proteção.

O motor conta com política estrita de **abstenção orientada a evidências**: quando uma consulta não atinge o limiar mínimo de similaridade com os textos oficiais, o sistema declara explicitamente a ausência de dados, orientando o usuário a procurar canais oficiais.

## Alternativas Consideradas
- **Respostas Diretas da LLM (Zero-shot / Few-shot):** Risco inaceitável de alucinação e falta de rastreabilidade.
- **Busca Web Aberta em Tempo Real (ex.: DuckDuckGo / SearXNG):** Introduz ruído de blogs comerciais de finanças, links patrocinados de bancos e potenciais conflitos de interesse.

## Consequências
- **Positivas:**
  - Respostas confiáveis, pedagógicas e auditáveis (cada resposta cita seu trecho documental).
  - Alinhamento rigoroso com o entregável da Semana 2 do Challenge 2.
- **Negativas / Riscos:**
  - O escopo de perguntas é limitado ao material bibliográfico indexado; temas altamente específicos fora da base demandarão novas ingestões curadas.
