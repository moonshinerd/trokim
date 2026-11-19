---
title: Trokim — Assistente Financeiro Pessoal com IA
---

<div class="tk-hero" markdown>

<img src="assets/hero-coin.png" class="tk-coin" alt="Moeda do Trokim com a onça-pintada, mascote do projeto" width="300" height="300">

# Entenda seu dinheiro. Decida com calma.

Assistente financeiro pessoal de código aberto, **local-first**: seus extratos ficam no seu aparelho, os números são calculados por código e as orientações vêm de fontes oficiais (BCB, CVM e CFPB).

[Conhecer a solução](apresentacao.md){ .md-button .md-button--primary }
[Guia de uso](guia-de-uso.md){ .md-button }

</div>

*Challenge 2 — Big Idea: Qualidade de Vida. "Empoderando pessoas com IA para compreender melhor, decidir melhor e viver melhor."*

O **Trokim** é um assistente financeiro de código aberto (*open-source*) projetado com foco em privacidade (*local-first*), explicabilidade determinística e fundamentação estrita em educação financeira oficial.

---

## Destaques do Projeto (Entregas 1 a 4 Concluídas)

<div class="grid cards" markdown>

-   :material-database-search:{ .lg .middle } **Base RAG Oficial com 20 Documentos**

    ---

    Acervo curado com metadados e hashes de órgãos reguladores: **BCB**, **CVM**, **CFPB** e **ANPD**.
    [:octicons-arrow-right-24: Ver Catálogo de Fontes](rag/catalogo.md)

-   :material-chart-line-variant:{ .lg .middle } **Benchmark RAG Auditado**

    ---

    **98,78%** de Recall@3, **95,12%** de resposta fundamentada e **100% de abstenção ativa** em casos fora de escopo (61 casos da Semana 2).
    [:octicons-arrow-right-24: Ver Métricas e Calibração](rag/index.md)

-   :material-scale-balance:{ .lg .middle } **Comparação LLM × RAG com Gráficos**

    ---

    Três abordagens em 30 casos, com revisão manual e **histórico versionado de execuções**: a fundamentação em evidências reduziu as alucinações confirmadas de 30,0% (piso) para 13,3% e 6,7%.
    [:octicons-arrow-right-24: Ver Resultados e Gráficos](pesquisa/resultados.md)

-   :material-account-group:{ .lg .middle } **Sistema Multiagente com Validação**

    ---

    Research, Analysis, Communication e Validation Agent em sequência: o Validation barra número sem suporte e conselho fora de escopo, e as **5 armadilhas injetadas foram barradas** em todas as execuções.
    [:octicons-arrow-right-24: Ver Agentes](agentes/index.md)

-   :material-tag-multiple:{ .lg .middle } **Categorização pela Atividade da Loja**

    ---

    Índice local de 22 milhões de CNPJs pela atividade econômica (CNAE) e 746 redes conhecidas: a categorização dos lançamentos reais foi de 56% para **67%** (89% sem as transferências Pix a pessoas).
    [:octicons-arrow-right-24: Ver ADR 0020](adr/0020-categorizacao-por-cnae.md)

-   :material-calculator:{ .lg .middle } **Cálculos 100% Determinísticos**

    ---

    Zero alucinação matemática. Lançamentos, balanços e médias são computados por motor estrito em Python.
    [:octicons-arrow-right-24: Ver ADR 0004](adr/0004-calculos-deterministicos.md)

-   :material-cellphone:{ .lg .middle } **Mobile Flutter & Local-First**

    ---

    App Android integrado à API local: resumo e extratos com os números calculados pelo backend, importação de OFX e PDF, chat com fontes citadas e histórico de conversas.
    [:octicons-arrow-right-24: Ver Guia de Uso](guia-de-uso.md)

</div>

---

## O Problema

Pessoas que utilizam múltiplas contas bancárias e cartões de crédito enfrentam atrito constante para:
1. Reunir e consolidar transações financeiras dispersas;
2. Compreender padrões reais de despesas sem comprometer horas em planilhas complexas;
3. Antecipar fechamentos de fatura e compromissos futuros;
4. Escolher conscientemente entre metas de poupança/investimento e despesas que promovem qualidade de vida.

---

## Essential Question

> **"Como a inteligência artificial pode ajudar as pessoas a compreender e planejar suas finanças pessoais, tomando decisões informadas sem comprometer sua qualidade de vida?"**

---

## Princípios Arquiteturais e de Projeto

- **Privacidade Local-First (LGPD):** O processamento de extratos bancários (arquivos OFX e faturas PDF) ocorre no ambiente do próprio usuário, sem exposição de dados sensíveis na nuvem: a API roda na máquina do usuário, os lançamentos importados ficam na memória dela e a base de conhecimento fica em SQLite local.
- **Cálculo Determinístico:** Valores numéricos, totais, saldos e projeções são computados com precisão por código matemático estrito (`calculation_service.py`). Modelos de Linguagem (LLMs) atuam apenas como camada de síntese e explicação pedagógica.
- **RAG com Fontes Oficiais:** Todas as orientações orçamentárias baseiam-se em referências consagradas de órgãos reguladores (**Banco Central do Brasil**, **CVM** e **CFPB**). Quando não há evidência empírica ou o tema envolve especulação, o agente se abstém ativamente.
- **Transparência e Rastreabilidade:** Cada requisito e decisão técnica possui vínculo direto com uma *Guiding Question* (GQ) e um registro de decisão arquitetural (*ADR*).

---

## Estrutura do Sistema

```mermaid
graph TD
    User([Usuário / Android]) -->|Extratos OFX / PDF| Mobile[App Flutter Trokim]
    Mobile -->|API REST Local| API[Backend FastAPI]
    
    subgraph "Camada de Aplicação (Local-First)"
        API --> Parser[Parser OFX & PDF]
        API --> Calc[Serviço de Cálculo Determinístico]
        API --> RAG[Mecanismo RAG Híbrido: FastEmbed + SQLite-Vec]
        API --> DB[(SQLite Local: vetores e metadados da base<br/>ORM + migrações Alembic)]
        API --> Gen[Síntese Generativa<br/>LLMProvider: LiteLLM, Ollama local ou mock]
        Gen --> RAG
        API --> Orq[Orquestrador multiagente<br/>Research → Analysis → Communication → Validation]
        Orq --> RAG
        Orq --> Calc
        Orq --> Gen
        Parser --> Cat[Categorização<br/>formatos dos bancos + índice CNPJ/CNAE local]
    end

    subgraph "Base de Conhecimento Regulada"
        RAG --> BCB[Caderno de Cidadania - BCB]
        RAG --> CVM[Portal do Investidor - CVM]
        RAG --> CFPB[Financial Well-Being - CFPB]
        RAG --> ANPD[Diretrizes de Privacidade - ANPD]
    end
```

---

## Navegação Rápida

- [Apresentação Executiva e Resultados](apresentacao.md)
- [Planejamento e Roadmap do CBL (Semanas 1 a 7)](planejamento.md)
- [Perguntas Norteadoras (Guiding Questions)](pesquisa/guiding-questions.md)
- [Requisitos do Sistema e MoSCoW](requisitos.md)
- [Arquitetura e Mapa do Sistema](arquitetura/mapa-do-sistema.md)
- [Base RAG e Benchmark da Semana 2](rag/index.md)
- [Comparação LLM × RAG (Semana 3)](pesquisa/comparacao-llm-rag.md)
- [Histórico de Resultados e Gráficos](pesquisa/resultados.md)
- [Guia de Uso](guia-de-uso.md)
- [Glossário](glossario.md)
- [Catálogo dos 20 Documentos Oficiais](rag/catalogo.md)
- [Atas de Reunião da Equipe](atas/index.md)
- [Decisões Arquiteturais (ADRs)](adr/index.md)
