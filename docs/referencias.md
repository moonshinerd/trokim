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

## 5. Parsers e exemplos públicos de faturas e extratos

Não há fatura real publicada (ela traz CPF, endereço e compras). Os layouts dos bancos experimentais ([ADR 0022](adr/0022-registro-de-perfis-e-niveis-de-suporte.md)) foram **lidos do código e das issues** de projetos abertos. **Nenhum código foi copiado:** só os padrões do formato (cabeçalhos, data, valor, parcela) viraram regras próprias do Trokim, testadas com texto sintético. Licenças não foram auditadas, o que reforça não copiar código. Em todos os casos, "não testado em arquivo real" vale também para nós.

| Ref | Repositório | Banco / formato | O que serviu ao Trokim |
|---|---|---|---|
| **[REF17]** | [thiagocolen/monday-money #67](https://github.com/thiagocolen/monday-money/issues/67) | Mercado Pago, extrato PDF | Colunas Data, Descrição, ID da operação, Valor, Saldo; data `DD-MM-AAAA`; descrição quebrada em várias linhas; cabeçalho que não se repete. |
| **[REF18]** | [crgasparoto-br/SolverFin #746](https://github.com/crgasparoto-br/SolverFin/pull/746) | Mercado Pago, extrato PDF | Conferir movimentos contra os saldos; rodapé não é lançamento. |
| **[REF19]** | [wendersoon/pdf_para_ofx_mercado_pago](https://github.com/wendersoon/pdf_para_ofx_mercado_pago) | Mercado Pago, extrato PDF | Resumo (Saldo inicial, Entradas, Saídas), valor `R$` com milhar por ponto. |
| **[REF20]** | [Gamegart/pdf-extractor-bank-data](https://github.com/Gamegart/pdf-extractor-bank-data) | Mercado Pago (México), PDF | Mostrou que o layout varia por país; não aproveitado. |
| **[REF21]** | [Rafaelrr5/financas-br](https://github.com/Rafaelrr5/financas-br) | Inter, fatura e extrato PDF | Marcador "Despesas da fatura"; linha com `+` é crédito; pagamento aparece como saída no extrato. |
| **[REF22]** | [cranzss/importaFatura](https://github.com/cranzss/importaFatura) | Inter, fatura PDF | Data `12 de nov. 2026`, parcela `(Parcela NN de NN)`, total da fatura e vencimento. |
| **[REF23]** | [Kiq98/pybank](https://github.com/Kiq98/pybank) | Inter, Nubank, BB e outros, PDF | Detecção do banco pelo conteúdo e conferência do total. |
| **[REF24]** | [uoyj/fatura-viewer-parser](https://github.com/uoyj/fatura-viewer-parser) | Itaú, Mercado Pago, Nubank, PDF | Arquitetura de um parser por banco e versão (inspirou o registro). |
| **[REF25]** | [ThomazMasayuki/extrator_fatura](https://github.com/ThomazMasayuki/extrator_fatura) | Genérico, PDF | Parcela `NN/NN`, senha só em memória, pagamento fora da soma. |
| **[REF26]** | [luizhumbertobove-ops/dash-fatura](https://github.com/luizhumbertobove-ops/dash-fatura) | Itaú, fatura PDF | Duas colunas, seções "Lançamentos: compras e saques" e "próximas faturas", ano pelo vencimento. |
| **[REF27]** | [gmega/parser-fatura-itau](https://github.com/gmega/parser-fatura-itau) | Itaú, fatura PDF e OFX | Âncora `Emissão: DD/MM/AAAA` para o ano; OFX 1.x em latin-1. |
| **[REF28]** | [devfelipepinho/extrator-fatura-itau-pdf](https://github.com/devfelipepinho/extrator-fatura-itau-pdf) | Itaú, fatura PDF | Linha `DD/MM descrição valor` (e o alerta de que o milhar quebra regex ingênua). |
| **[REF29]** | [dm1nduc42/projetoCartao](https://github.com/dm1nduc42/projetoCartao) | PicPay, fatura PDF | `Picpay Card final NNNN`, `Vencimento: DD-MM-AAAA`, `PARC NN/NN`, linhas "Subtotal". |
| **[REF30]** | [BenKefa/Ler_Extrato_Git](https://github.com/BenKefa/Ler_Extrato_Git) | PicPay, fatura PDF | Cabeçalho "Data / Estabelecimento / Valor"; "PAGAMENTO DE FATURA" fora dos totais. |
| **[REF31]** | [danilopopeye/c6bank-transactions](https://github.com/danilopopeye/c6bank-transactions) | C6 Bank, fatura CSV | Separador `;`, colunas Data, Nome no Cartão, Final do Cartão, Categoria, Descrição, Parcela (`Única` ou `N/M`), Valor (em US$), Cotação, Valor (em R$). |

## 6. Créditos de Arte

- **Mascote (onça-pintada):** estilizado a partir do vetor *Jaguar SVG*, de Jordan Irwin (AntumDeluge), publicado em [OpenGameArt](https://opengameart.org/node/98089) sob **CC0 (domínio público)**. Atribuição não é obrigatória; fica aqui por boa prática. O Trokim removeu o cenário, ampliou a área de desenho e recolorou a arte em tons dourados com as manchas vazadas.
- **Tipografia:** [Plus Jakarta Sans](https://fonts.google.com/specimen/Plus+Jakarta+Sans), licença SIL Open Font License 1.1 (arquivo embarcado no site em `docs/assets/fonts/` e no app, sem requisição ao Google Fonts).
