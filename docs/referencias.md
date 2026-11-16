# Referências e Fontes da Pesquisa

Catálogo consolidado de referências bibliográficas, materiais institucionais regulamentados, legislações e documentações técnicas que fundamentam o desenvolvimento do **Trokim**.

---

## 1. Órgãos Reguladores e Educação Financeira

| Ref | Documento / Título | Instituição | Link Oficial Clicável | Aplicação no Trokim |
|---|---|---|---|---|
| **[REF01]** | **Challenge 2 — Big Idea: Qualidade de Vida** | TIC-IA / Insper (2026) | *Material fornecido pela disciplina* | Definição da Big Idea, Roadmap de 7 semanas e metodologia CBL. |
| **[REF02]** | **Caderno de Cidadania Financeira** | Banco Central do Brasil (BCB) | [bcb.gov.br/.../caderno_cidadania_financeira.pdf](https://www.bcb.gov.br/pre/pef/port/caderno_cidadania_financeira.pdf) | Conceituação de orçamento familiar, diagnóstico, despesas fixas/variáveis e reserva de emergência. |
| **[REF03]** | **Portal do Investidor: Organização e Planejamento** | Comissão de Valores Mobiliários (CVM) | [gov.br/investidor/.../antes-de-investir](https://www.gov.br/investidor/pt-br/investir/antes-de-investir) | Metas de curto, médio e longo prazo, perfil de tolerância a risco e preservação de patrimônio. |
| **[REF04]** | **Portal do Investidor: Momentos da Vida** | Comissão de Valores Mobiliários (CVM) | [gov.br/investidor/pt-br](https://www.gov.br/investidor/pt-br) | Planejamento em fases de transição financeira e diversificação de ativos. |
| **[REF05]** | **Financial Well-Being Scale: User Guide** | Consumer Financial Protection Bureau (CFPB) | [consumerfinance.gov/.../financial-well-being-scale](https://www.consumerfinance.gov/data-research/research-reports/financial-well-being-scale/) | Instrumento psicométrico de bem-estar financeiro, sensação de controle e liberdade de escolha. |
| **[REF06]** | **Chatbots in Consumer Finance (Relatório 2023)** | Consumer Financial Protection Bureau (CFPB) | [consumerfinance.gov/.../chatbots-in-consumer-finance](https://www.consumerfinance.gov/data-research/research-reports/chatbots-in-consumer-finance/) | Mapeamento de riscos de alucinação, aconselhamento inadequado e salvaguardas de IA financeira. |

---

## 2. Legislação, Privacidade e Dados (LGPD)

| Ref | Norma / Guia | Órgão Regulador | Link Oficial Clicável | Aplicação no Trokim |
|---|---|---|---|---|
| **[REF07]** | **Lei Geral de Proteção de Dados (Lei nº 13.709/2018)** | Presidência da República / Brasil | [planalto.gov.br/.../lei/l13709.htm](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm) | Princípios de minimização de dados, finalidade estrita e fundamentação da arquitetura *local-first*. |
| **[REF08]** | **Guias Orientativos para Agentes de Tratamento** | Autoridade Nacional de Proteção de Dados (ANPD) | [gov.br/anpd/pt-br](https://www.gov.br/anpd/pt-br) | Diretrizes de segurança da informação e governança em protótipos de inteligência artificial. |
| **[REF09]** | **Documentação de API e Sandbox** | Pluggy Open Finance | [docs.pluggy.ai](https://docs.pluggy.ai/) | Análise de viabilidade comparativa entre Open Finance bancário e importação documental local. |

---

## 3. Inteligência Artificial, RAG e Processamento de Linguagem Natural

| Ref | Estudo / Documentação | Autores / Provedor | Link Oficial Clicável | Aplicação no Trokim |
|---|---|---|---|---|
| **[REF10]** | **Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks** | Lewis et al. (Facebook AI Research, 2020) | [arxiv.org/abs/2005.11401](https://arxiv.org/abs/2005.11401) | Fundamentação teórica do mecanismo RAG utilizado na Semana 2 para ancoragem das respostas. |
| **[REF11]** | **Tool Calling Capabilities** | Ollama Documentation | [docs.ollama.com/.../tool-calling](https://docs.ollama.com/capabilities/tool-calling) | Integração estruturada entre modelos de linguagem locais e funções determinísticas de cálculo. |
| **[REF12]** | **Structured Outputs and JSON Mode** | Ollama Documentation | [docs.ollama.com/.../structured-outputs](https://docs.ollama.com/capabilities/structured-outputs) | Extração e formatação estrita de entidades financeiras a partir de prompts em linguagem natural. |

---

## 4. Métricas de Validação e Aprendizado de Máquina (Scikit-Learn)

| Ref | Função / Métrica | Biblioteca | Link Oficial Clicável | Aplicação no Trokim |
|---|---|---|---|---|
| **[REF13]** | **F1 Score (Macro & Weighted)** | Scikit-Learn Metrics | [scikit-learn.org/.../sklearn.metrics.f1_score.html](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.f1_score.html) | Avaliação da precisão de categorização automática das transações bancárias (RF09). |
| **[REF14]** | **Mean Absolute Error (MAE)** | Scikit-Learn Metrics | [scikit-learn.org/.../sklearn.metrics.mean_absolute_error.html](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.mean_absolute_error.html) | Mensuração do erro absoluto em reais nas projeções de despesas futuras (GQ09 / GQ11). |
| **[REF15]** | **Mean Absolute Percentage Error (MAPE)** | Scikit-Learn Metrics | [scikit-learn.org/.../sklearn.metrics.mean_absolute_percentage_error.html](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.mean_absolute_percentage_error.html) | Mensuração do erro relativo percentual em estimativas orçamentárias. |
| **[REF16]** | **TimeSeriesSplit (Validação Cruzada)** | Scikit-Learn Model Selection | [scikit-learn.org/.../sklearn.model_selection.TimeSeriesSplit.html](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) | Divisão temporal sem vazamento de dados do futuro para avaliação de séries financeiras. |

## 5. Créditos de Arte

- **Mascote (onça-pintada):** estilizado a partir do vetor *Jaguar SVG*, de Jordan Irwin (AntumDeluge), publicado em [OpenGameArt](https://opengameart.org/node/98089) sob **CC0 (domínio público)**. Atribuição não é obrigatória; fica aqui por boa prática. O Trokim removeu o cenário, ampliou a área de desenho e recolorou a arte em tons dourados com as manchas vazadas.
- **Tipografia:** [Plus Jakarta Sans](https://fonts.google.com/specimen/Plus+Jakarta+Sans), licença SIL Open Font License 1.1.
