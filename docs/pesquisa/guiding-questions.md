# Perguntas Norteadoras da Pesquisa (Guiding Questions)

O portfólio de pesquisa e engenharia de requisitos do **Trokim** foi construído ao longo das fases *Engage* e *Investigate* da metodologia **Challenge Based Learning (CBL)**, no âmbito do **Challenge 2 (Qualidade de Vida / TIC-IA 2026)**.

As **13 Perguntas Norteadoras (GQ01 a GQ13)** estruturam as hipóteses investigadas, as evidências bibliográficas e regulatórias levantadas e as decisões de arquitetura e mitigação de risco que fundamentam o MVP.

> Para consultar o catálogo completo de fontes com autores, normas e links regulamentares, acesse a página de [Referências da Pesquisa](../referencias.md).

---

## GQ01 — Como a inteligência artificial atuará de forma prática para empoderar o usuário a "compreender melhor, decidir melhor e viver melhor" a sua rotina financeira?

> **Hipótese:** O problema financeiro considerado pelo projeto é a dificuldade para acompanhar várias contas e cartões, saber quanto já havia sido gasto e antecipar a fatura. A hipótese inicial do grupo era que reunir essas informações e explicá-las com IA aumentaria a clareza sobre entradas, saídas e gastos recorrentes. O desconforto com a falta de clareza financeira motiva a proposta, mas não demonstra que o aplicativo reduzirá ansiedade ou melhorará a saúde. A pergunta de pesquisa é se transformar dados dispersos em um retrato verificável ajuda a compreender a situação, comparar escolhas e planejar com mais controle.

### Dados Encontrados e Fundamentação Científica
- O [Caderno de Cidadania Financeira do Banco Central](https://www.bcb.gov.br/pre/pef/port/caderno_cidadania_financeira.pdf) apresenta o orçamento como instrumento de registro, organização e avaliação de receitas e despesas. A CVM, em Defina seus objetivos, relaciona o planejamento às prioridades de vida da família. Essas referências sustentam partir dos dados e das metas informadas pelo usuário, em vez de oferecer sugestões genéricas.

- O CFPB define bem-estar financeiro por controle cotidiano, capacidade de enfrentar imprevistos, progresso em metas e liberdade de escolha. Seu relatório [Chatbots in Consumer Finance (CFPB)](https://www.consumerfinance.gov/data-research/research-reports/chatbots-in-consumer-finance/) também registra riscos de respostas inexatas e assistência insuficiente. Logo, conversar com uma IA ou reduzir gastos não comprova, por si só, melhora na qualidade de vida. A aplicação ao Pierre é uma hipótese de projeto, não um resultado demonstrado por essas publicações.

### Decisão de Engenharia no Trokim
A conclusão desta pergunta norteadora estabelece que:
Propõe-se um MVP local centrado em um percurso completo: importar e revisar dados, compreender um resumo, comparar dois cenários e registrar uma meta escolhida pelo usuário. A IA será uma interface de explicação e apoio à decisão, com cálculos verificáveis e referências educacionais recuperadas pela base de conhecimento. O protótipo não executará pagamentos nem contratará produtos financeiros. Para a entrega documental de sexta-feira, esse percurso descreve o escopo e a forma de avaliação; não representa uma funcionalidade já implementada.

Esta decisão está formalizada no repositório através de: [ADR 0003](../adr/0003-rag-fontes-oficiais.md), [ADR 0004](../adr/0004-calculos-deterministicos.md).

### Matriz de Decisão e Critérios do Sistema

| Dimensão de Apoio | Abordagem Convencional de Mercado | Padrão Adotado no Trokim |
|---|---|---|
| **Interface com o Usuário** | Chatbot conversacional aberto sem cálculo prévio | Cálculos matemáticos determinísticos prévios explicados pela IA |
| **Conselho Financeiro** | Sugestões genéricas ou especulativas de corte de gastos | Apoio à decisão com cenários ajustáveis pelo usuário |
| **Ações Financeiras** | Promessas de automação bancária desassistida | Escopo estritamente consultivo, sem movimentação de dinheiro no MVP |

### Rastreabilidade
- **Requisitos Associados:** RF05, RF07, RNF01
- **ADRs Vinculadas:** [ADR 0003](../adr/0003-rag-fontes-oficiais.md), [ADR 0004](../adr/0004-calculos-deterministicos.md)

---

## GQ02 — Como delimitar o escopo da integração com o Open Finance para garantir a entrega das tecnologias exigidas pelo roadmap, como o primeiro mecanismo RAG na semana 2, o sistema multiagentes na semana 4 e os agentes multimodais na semana 5?

> **Hipótese:** A proposta inicial considerava conectar contas bancárias e analisar transações com IA. Como alternativa de integração, foi avaliada a [Pluggy Sandbox API](https://docs.pluggy.ai/), em comparação com o fluxo de importação manual. Também foi considerada a fricção de exigir cadastro e === PAGE 22 === autorização em serviço externo. A hipótese inicial era preservar a facilidade de reunir contas sem deixar que a obtenção dos dados consumisse o prazo do projeto. A alternativa de solução local reformula essa hipótese; ela não torna irrelevante a dificuldade de uso da importação manual.

### Dados Encontrados e Fundamentação Científica
- A documentação da [Pluggy Sandbox API](https://docs.pluggy.ai/) confirma os mecanismos de integração, credenciais e autenticação. Na página oficial de preços, consultada em 28/10/2026, o plano Dados aparece a partir de R$

- A referência da API descreve conectores de sandbox que simulam instituições. Esse ambiente permite testar um fluxo, mas não demonstra acesso gratuito e permanente a contas reais. A alternativa deve ser descrita como prova técnica, com condições verificadas na documentação e no contrato, em vez de transformar o limite de contas citado na conversa em uma regra de produção.

### Decisão de Engenharia no Trokim
A conclusão desta pergunta norteadora estabelece que:
A hipótese final é priorizar processamento documental local e adiar a integração bancária real. No cronograma proposto, a semana 1 concentra escopo e dados sintéticos; a semana 2 entrega o primeiro RAG com fontes; a semana 3 integra importação e validação; a semana 4 entrega agentes de categorização, análise e planejamento com responsabilidades definidas; a semana 5 entrega um agente multimodal para PDF ou imagem de documento; e as semanas 6 e 7 concentram avaliação e integração. Esse recorte preserva as entregas de IA mencionadas na pergunta e mantém a obtenção dos dados sob controle. A viabilidade de desempenho e o hardware serão verificados nos testes.

Esta decisão está formalizada no repositório através de: [ADR 0005](../adr/0005-importacao-local-ofx-pdf.md).

### Matriz de Decisão e Critérios do Sistema

| Canal de Entrada | Vantagens Avaliadas | Decisão no MVP do Trokim |
|---|---|---|
| **Open Finance ([Pluggy Sandbox API](https://docs.pluggy.ai/) / Klavi)** | Sincronização bancária direta e automática | Postergado pós-MVP para evitar atrito de autorização e dependência externa |
| **Importação Manual OFX / PDF** | Privacidade total, dados sob controle do usuário, zero credencial externa | Padrão Adotado no MVP. Processamento documental local |
| **Dados Sintéticos (Semana 1-2)** | Conformidade absoluta com LGPD e validação com gabarito conhecido | Padrão Adotado para todos os testes e demonstrações |

### Rastreabilidade
- **Requisitos Associados:** RF01, RF02, RNF01
- **ADRs Vinculadas:** [ADR 0005](../adr/0005-importacao-local-ofx-pdf.md)

---

## GQ03 — Quais são os stakeholders primários do projeto e quais os riscos técnicos e de privacidade (como viés e proteção de dados/LGPD) ao conectar contas bancárias reais, focando nas definições iniciais exigidas para a semana 1?

> **Hipótese:** O público considerado pelo projeto inclui pessoas que têm dados financeiros dispersos e querem compreender sua rotina; a equipe também se reconhece nessa dor. A hipótese inicial é que esses usuários são o público prioritário para validar a utilidade, enquanto a equipe assume desenvolvimento e testes. Instituições financeiras e integradores só entram no fluxo se houver conexão real. A identificação de quem trata os dados e de quais riscos isso cria precisa acompanhar a arquitetura escolhida; não pode ser deduzida apenas da intenção de conectar bancos. Além disso, criar contas e autorizar conexões em outro serviço pode dificultar a experiência do usuário, o que inclui esse fornecedor no mapeamento apenas se a integração for realmente adotada.

### Dados Encontrados e Fundamentação Científica
- A pesquisa indica que é necessário distinguir tratamento de dados pessoais, participação regulada em Open Finance e decisões de arquitetura. Os riscos não tornam todo protótipo uma instituição financeira. As evidências abaixo orientam o recorte inicial e deverão ser aplicadas conforme o fluxo efetivo de dados.

- A LGPD prevê finalidade, necessidade, transparência, segurança e não discriminação; a base legal depende do tratamento. Dados financeiros não integram automaticamente a definição legal de dados sensíveis. O art. 38 permite à autoridade === PAGE 23 === determinar um RIPD, sem torná-lo obrigação automática para todo protótipo. Fonte: LGPD, arts. 5º, 6º, 7º, 11, 38 e

### Decisão de Engenharia no Trokim
A conclusão desta pergunta norteadora estabelece que:
A hipótese final é validar o assistente com arquivos importados e processamento local, mantendo Open Finance real como integração futura ou prova em sandbox. Usuários e equipe de desenvolvimento são os atores centrais; fornecedores e reguladores têm papéis externos conforme o uso adotado. A redução de dependências não dispensa testar proteção dos dados, qualidade das respostas e controle do usuário.

Esta decisão está formalizada no repositório através de: [ADR 0002](../adr/0002-fastapi-sqlite-local.md), [ADR 0005](../adr/0005-importacao-local-ofx-pdf.md).

### Matriz de Decisão e Critérios do Sistema

| Risco Identificado | Severidade | Medida de Mitigação Implementada |
|---|---|---|
| **Vazamento de dados em logs / nuvem** | Crítica | Arquitetura local-first. SQLite local sem envio de extratos para APIs externas |
| **Exposição de dados reais de alunos/usuários** | Alta | Uso estrito de geradores sintéticos em research/synthetic_data/ |
| **Erros de parsing e duplicatas em faturas** | Média | Algoritmo determinístico de deduplicação e conferência visual no app |

### Rastreabilidade
- **Requisitos Associados:** RNF01, RNF05, RNF06
- **ADRs Vinculadas:** [ADR 0002](../adr/0002-fastapi-sqlite-local.md), [ADR 0005](../adr/0005-importacao-local-ofx-pdf.md)

---

## GQ04 — Quais métricas objetivas de negócio e de sistema serão utilizadas para avaliar e validar a eficácia do planejamento gerado pela IA na tomada de decisão do usuário?

> **Hipótese:** A proposta parte de que a solução precisa melhorar a experiência cotidiana, e não apenas demonstrar uma técnica de IA, e trouxe como problema concreto a dificuldade de entender gastos em várias contas. Para esta pergunta, a hipótese derivada é que uma demonstração bem-sucedida precisa combinar cálculos corretos com compreensão e uma decisão mais informada. As métricas e o protocolo abaixo são propostas desta análise; não devem ser apresentados como resultados ou critérios formalmente validados. O projeto prioriza tratar os dados para o usuário, em vez de concentrar o esforço no módulo de obtenção. Isso orienta medir a passagem do arquivo bruto para uma informação compreensível.

### Dados Encontrados e Fundamentação Científica
- A documentação do scikit-learn oferece MAE para medir erro absoluto de previsões e F1 para combinar precisão e revocação na classificação. Já a [Financial Well-Being Scale do CFPB](https://www.consumerfinance.gov/data-research/research-reports/financial-well-being-scale/) mede uma dimensão percebida de bem-estar, distinta da exatidão técnica. Essas fontes justificam avaliar o funcionamento do sistema e a experiência do usuário separadamente.

- Para a qualidade dos dados, propõe-se medir a proporção de transações importadas corretamente, a taxa de duplicatas e a quantidade de divergências encaminhadas à revisão. Um conjunto de arquivos sintéticos terá datas, descrições e valores conhecidos para comparação. A conciliação usará valores em centavos e considerará saldo anterior, créditos, juros e ajustes quando existirem; a soma simples das compras não será imposta a todo tipo de extrato ou fatura.

### Decisão de Engenharia no Trokim
A conclusão desta pergunta norteadora estabelece que:
Propõe-se começar com três cenários financeiros sintéticos e vinte perguntas com respostas e fontes de referência. Como critérios iniciais de aceite, todas as somas determinísticas do conjunto deverão coincidir com o gabarito; nenhuma divergência de conciliação poderá ser aceita silenciosamente; e toda resposta educacional deverá trazer uma fonte que sustente a afirmação ou reconhecer a falta de evidência. Esses critérios são escolhas do projeto, não patamares extraídos de estudos. === PAGE 24 ===

Esta decisão está formalizada no repositório através de: [ADR 0004](../adr/0004-calculos-deterministicos.md).

### Matriz de Decisão e Critérios do Sistema

| Métrica | Definição Técnica | Meta no MVP |
|---|---|---|
| **Taxa de Importação Correta** | Lançamentos com data, valor e descrição corretos / total gabarito | 100% nos extratos sintéticos padronizados |
| **Acurácia Numérica** | Saldos e totais por categoria computados sem desvio aritmético | 100% garantido por testes determinísticos com pytest |
| **Taxa de Fundamentação RAG** | Respostas sustentadas por citação documental oficial / total consultas | >= 90% em consultas no domínio |

### Rastreabilidade
- **Requisitos Associados:** RF03, RNF02, RNF06
- **ADRs Vinculadas:** [ADR 0004](../adr/0004-calculos-deterministicos.md)

---

## GQ05 — Qual base de conhecimento estruturada e confiável (ex: diretrizes de educação financeira, perfis de investimento) o sistema consumirá para comparar cenários, gerar respostas baseadas em evidências e evitar alucinações?

> **Hipótese:** A proposta associa o assistente à análise de gastos e à possibilidade de modelos preditivos, mas informações bancárias, sozinhas, não fornecem uma base educacional sobre como planejar. A hipótese inicial derivada é separar o conhecimento sobre finanças pessoais dos dados de cada usuário. O sistema precisará de referências identificáveis para explicar conceitos e de registros revisados para calcular valores. O corpus descrito a seguir é uma seleção de pesquisa para o MVP, não uma base já definida ou carregada pelo grupo. As propostas de ferramentas precisam ser confrontadas com suas documentações.

### Dados Encontrados e Fundamentação Científica
- O [Caderno de Cidadania Financeira do Banco Central](https://www.bcb.gov.br/pre/pef/port/caderno_cidadania_financeira.pdf) reúne conteúdos sobre orçamento, crédito, consumo, poupança e prevenção de riscos. A CVM oferece materiais sobre organização financeira, objetivos e reserva para emergências. Esses conteúdos são candidatos ao corpus inicial por sua autoria institucional e relação direta com o escopo do MVP.

- O artigo de Lewis e colaboradores sobre Retrieval-Augmented Generation descreve a combinação de geração com recuperação de documentos externos. Isso fundamenta a escolha de RAG como abordagem a testar, mas não demonstra que qualquer aplicação financeira ficará correta. O relatório do CFPB sobre chatbots registra riscos de inexatidão; por isso, citar uma página só será útil quando o trecho recuperado sustentar a resposta.

### Decisão de Engenharia no Trokim
A conclusão desta pergunta norteadora estabelece que:
Propõe-se um RAG local com corpus institucional pequeno, versionado e verificável. A resposta deverá exibir o nome da fonte com link direto e, quando disponível, a página ou seção utilizada. Se a evidência for insuficiente, o Pierre deverá informar isso e solicitar os dados que faltam. Essa é uma especificação de comportamento a implementar e avaliar; não uma garantia de eliminação de alucinações.

Esta decisão está formalizada no repositório através de: [ADR 0003](../adr/0003-rag-fontes-oficiais.md).

### Matriz de Decisão e Critérios do Sistema

| Fonte Oficial | Publicação de Referência | Uso no Sistema |
|---|---|---|
| **Banco Central do Brasil (BCB)** | Caderno de Cidadania Financeira | Diretrizes de orçamento familiar, reserva de emergência e dívidas |
| **Comissão de Valores Mobiliários (CVM)** | Portal do Investidor (Metas e Prazos) | Planejamento financeiro de curto/médio/longo prazo e diversificação |
| **CFPB (EUA)** | [Financial Well-Being Scale do CFPB](https://www.consumerfinance.gov/data-research/research-reports/financial-well-being-scale/) & Chatbot Report | Pilares de qualidade de vida e salvaguardas contra alucinação de IA |

### Rastreabilidade
- **Requisitos Associados:** RF05, RF06, RF10
- **ADRs Vinculadas:** [ADR 0003](../adr/0003-rag-fontes-oficiais.md)

---

## GQ06 — Como a inteligência artificial pode ajudar as pessoas a gerenciar melhor suas finanças pessoais sem comprometer sua qualidade de vida?

> **Hipótese:** Qualidade de vida é tratada neste projeto como algo amplo e dependente da pessoa, incluindo saúde, relações, produtividade e previsibilidade financeira. Depois, delimitou uma dor financeira concreta. A hipótese inicial é que ajudar a organizar o dinheiro pode contribuir para essa dimensão da vida, mas não substitui todas as outras. O planejamento deve ser compatível com prioridades individuais; reduzir gastos indiscriminadamente não equivale a melhorar a vida.

### Dados Encontrados e Fundamentação Científica
- A página Organize a sua vida financeira, da CVM, relaciona organização, despesas presentes e objetivos futuros. Já a definição de bem-estar financeiro do CFPB inclui liberdade de escolha. Essas referências apoiam avaliar a adequação do planejamento à vida do usuário, sem presumir que toda economia represente melhora. === PAGE 25 ===

- No Pierre, propõe-se que o usuário informe compromissos, metas e despesas que deseja preservar. A IA explicará onde há margem de ajuste e comparará alternativas calculadas pelo sistema. Se o orçamento não comportar uma meta, deverá mostrar a insuficiência e permitir rever o prazo ou o objetivo. A prioridade atribuída a uma despesa será declarada pela pessoa, sem ser inferida apenas pelo estabelecimento.

### Decisão de Engenharia no Trokim
A conclusão desta pergunta norteadora estabelece que:
O MVP deverá produzir um plano ajustável e compreensível, preservando a decisão do usuário. A utilidade será testada por tarefas e perguntas de compreensão; a contribuição para qualidade de vida será uma hipótese de acompanhamento. O percurso operacional está detalhado na pergunta 1 e os indicadores, nas perguntas 4 e

Esta decisão está formalizada no repositório através de: [ADR 0004](../adr/0004-calculos-deterministicos.md).

### Matriz de Decisão e Critérios do Sistema

| Premissa | Risco Abordado | Solução no Trokim |
|---|---|---|
| **Regra Rígida 50-30-20** | Inaplicável para rendas variáveis ou orçamentos deficitários | Simulação de cenários flexíveis definidos pelo usuário |
| **Corte Indiscriminado de Despesas** | Degradação da saúde mental e sensação de punição | Preservação explícita de itens de bem-estar e lazer |
| **Autonomia Decisória** | IA impondo metas irreais de economia | A IA atua como conselheira reflexiva; o usuário escolhe a meta |

### Rastreabilidade
- **Requisitos Associados:** RF08, RNF01
- **ADRs Vinculadas:** [ADR 0004](../adr/0004-calculos-deterministicos.md)

---

## GQ07 — Como a IA pode identificar padrões de consumo e oportunidades de economia a partir dos dados financeiros dos usuários?

> **Hipótese:** Os exemplos iniciais foram saber quanto entrou na conta, quanto foi transferido e quanto se gasta com transporte, alimentação e outras despesas fixas. A hipótese inicial era que detalhar esses movimentos já entregaria valor mesmo antes de uma previsão avançada. Para tornar isso testável, o sistema deverá distinguir categoria, origem e período, sem contar duas vezes o mesmo gasto quando a fatura e seu pagamento aparecem em arquivos diferentes. O desenho proposto distingue categorização e análise.

### Dados Encontrados e Fundamentação Científica
- A CVM, em Para onde vai o seu dinheiro, destaca a importância de conhecer a distribuição dos gastos. Para avaliar a classificação automática, a documentação de F1 do scikit-learn fornece uma medida que combina precisão e revocação. Esses materiais sustentam organizar os dados e medir a qualidade das categorias antes de usar a classificação para sugerir mudanças.

- Propõe-se normalizar datas, valores, descrições e identificadores, detectar duplicatas e aplicar primeiro regras corrigíveis pelo usuário. Depois, o sistema calculará totais por categoria, variações entre períodos equivalentes e possíveis recorrências por descrição, intervalo e valor. Transferências internas e pagamento de fatura precisarão de tratamento específico para não duplicar despesas. Um mês parcial não será comparado diretamente a um mês completo sem aviso.

### Decisão de Engenharia no Trokim
A conclusão desta pergunta norteadora estabelece que:
O MVP começará com regras, agregações e revisão humana, usando a IA para os casos ambíguos. Cada padrão apresentado deverá permitir consultar as transações de origem. Uma possível recorrência será marcada como hipótese, e um aumento de gasto não será automaticamente classificado como desperdício. A escolha entre regras e modelos mais complexos dependerá dos erros observados no conjunto de avaliação.

Esta decisão está formalizada no repositório através de: [ADR 0004](../adr/0004-calculos-deterministicos.md).

### Matriz de Decisão e Critérios do Sistema

| Etapa do Pipeline | Mecanismo | Garantia de Qualidade |
|---|---|---|
| **Classificação Primária** | Heurística determinística de palavras-chave no histórico | Transparência total sobre a categoria inferida |
| **Deduplicação de Lançamentos** | Chave unificada (data, valor absoluto, descrição, tipo) | Evita dupla contagem entre fatura de cartão e débito bancário |
| **Casos Ambíguos** | Sinalização visual para conferência e ajuste no app Flutter | Controle humano no loop antes de consolidar métricas |

### Rastreabilidade
- **Requisitos Associados:** RF03, RF04, RF09
- **ADRs Vinculadas:** [ADR 0004](../adr/0004-calculos-deterministicos.md)

---

## GQ08 — Como desenvolver um sistema de recomendações personalizadas considerando renda, despesas, dívidas e objetivos pessoais?

> **Hipótese:** O escopo inicial prevê uma análise que faça sentido para a rotina financeira da pessoa, começando por entradas, transferências e gastos fixos. A hipótese derivada para recomendações é que os mesmos totais não justificam o mesmo plano para todos: compromissos, renda e prioridades precisam ser conhecidos. Ainda é necessário testar como transformar o diagnóstico em alternativas úteis. O desenho de regras e === PAGE 26 === cenários abaixo é uma proposta para esse passo, não uma decisão detalhada já registrada pelo grupo.

### Dados Encontrados e Fundamentação Científica
- A CVM, em Defina seus objetivos, coloca as prioridades de vida no centro do planejamento. Em Planeje os seus gastos, descreve o orçamento como projeção ajustável. A documentação de validadores do Pydantic permite definir verificações de campos e de conjuntos de dados; no projeto, essa capacidade poderá verificar as restrições calculáveis do plano, sem provar que a recomendação é adequada por si só.

- Propõe-se calcular a margem disponível depois das despesas e compromissos conhecidos, separar despesas essenciais das ajustáveis conforme escolha do usuário e simular alternativas de prazo ou contribuição mensal. Informações de dívida deverão incluir saldo, parcelas e custo quando disponíveis; sem esses dados, o sistema não afirmará qual dívida é a mais cara. A IA explicará as opções com os valores retornados pelo cálculo, solicitando confirmação quando houver lacunas.

### Decisão de Engenharia no Trokim
A conclusão desta pergunta norteadora estabelece que:
O primeiro recomendador será baseado em regras e cenários, com justificativa, premissas e possibilidade de correção. Não adotará um percentual universal obrigatório de poupança nem recomendará produtos de investimento. O teste verificará se o plano respeita as restrições declaradas e se o usuário entende a diferença entre as alternativas. Recursos mais sofisticados dependerão de evidência de utilidade além dessa referência simples.

Esta decisão está formalizada no repositório através de: [ADR 0003](../adr/0003-rag-fontes-oficiais.md), [ADR 0004](../adr/0004-calculos-deterministicos.md).

### Matriz de Decisão e Critérios do Sistema

| Componente | Função Técnica | Garantia de Rastreabilidade |
|---|---|---|
| **Motor de Diagnóstico** | Compara receitas, despesas fixas e variáveis calculadas | Sem alucinações numéricas |
| **Recuperador RAG** | Injeta princípios do BCB/CVM no prompt de contexto | Cada sugestão exibe a fonte oficial e seção citada |
| **Simulador Comparativo** | Gera dois cenários alternativos (Padrão vs. Otimizado) | Usuário visualiza o impacto exato na margem livre |

### Rastreabilidade
- **Requisitos Associados:** RF08, RF10
- **ADRs Vinculadas:** [ADR 0003](../adr/0003-rag-fontes-oficiais.md), [ADR 0004](../adr/0004-calculos-deterministicos.md)

---

## GQ09 — Como utilizar modelos preditivos para estimar despesas futuras e identificar possíveis desequilíbrios financeiros?

> **Hipótese:** Os modelos preditivos são considerados como extensão da análise financeira. A hipótese inicial é que conhecer o padrão de entradas e saídas permitirá antecipar despesas e desequilíbrios. A proposta, porém, não demonstra disponibilidade de histórico ou precisão de previsão. Portanto, a investigação precisa separar o que é compromisso conhecido, estimativa baseada no passado e evento que os dados não permitem prever. Priorizar o tratamento e a qualidade dos dados é necessário antes de afirmar desempenho preditivo.

### Dados Encontrados e Fundamentação Científica
- A CVM descreve o orçamento doméstico como projeção que permite antecipar ajustes. A documentação do TimeSeriesSplit alerta para o uso incorreto de dados futuros no treinamento de avaliações temporais. Já o MAE permite expressar o erro absoluto das previsões na unidade dos valores avaliados. Essas referências orientam uma projeção com premissas claras e teste em períodos posteriores.

- Propõe-se somar compromissos futuros conhecidos e estimar despesas variáveis a partir de períodos anteriores comparáveis. Saldo inicial e receitas previstas precisarão estar disponíveis e identificados; sem eles, o Pierre poderá projetar despesas, mas não prometer um saldo futuro completo. Eventos extraordinários serão separados das recorrências. Cenários conservador e habitual poderão variar premissas explícitas, sem apresentar faixas arbitrárias como intervalos estatísticos de confiança.

### Decisão de Engenharia no Trokim
A conclusão desta pergunta norteadora estabelece que:
O MVP utilizará inicialmente projeção por regras e uma referência como repetir o último período comparável. Modelos de regressão ou séries temporais só serão adotados se houver histórico suficiente e melhora observada em teste cronológico. Na ausência desse histórico, a entrega demonstrará a lógica com dados sintéticos e registrará que a precisão preditiva em uso real ainda não foi validada. === PAGE 27 ===

Esta decisão está formalizada no repositório através de: [ADR 0004](../adr/0004-calculos-deterministicos.md).

### Matriz de Decisão e Critérios do Sistema

| Tipo de Projeção | Complexidade | Abordagem no Trokim |
|---|---|---|
| **Linha de Base (Baseline)** | Repetição do último período comparável + despesas fixas conhecidas | Adotado como padrão auditável no MVP |
| **Modelos Estatísticos (ARIMA/Séries)** | Exigem histórico extenso de múltiplos meses para calibrar | Postergado para fases avançadas após validação do baseline |
| **Alertas de Desequilíbrio** | Notificação se despesas fixas excederem 70% das receitas médias | Regra explícita determinística com aviso pedagógico |

### Rastreabilidade
- **Requisitos Associados:** RF03, RF08
- **ADRs Vinculadas:** [ADR 0004](../adr/0004-calculos-deterministicos.md)

---

## GQ10 — Como integrar processamento de linguagem natural para permitir que os usuários consultem suas finanças por meio de conversas?

> **Hipótese:** Uma interface conversacional é uma possibilidade do projeto; o canal final e seu funcionamento ainda não foram definidos. A hipótese inicial derivada é que perguntas em linguagem cotidiana podem facilitar o acesso a informações como gastos e entradas. Para o MVP, a prioridade será testar a compreensão da pergunta e a correção da resposta; uma integração com aplicativo de mensagens dependerá de análise própria.

### Dados Encontrados e Fundamentação Científica
- A documentação do Ollama sobre tool calling descreve chamadas de ferramentas e uso de seus resultados nas respostas. A documentação de saídas estruturadas permite especificar um esquema JSON para a resposta do modelo. Esses recursos apoiam separar a interpretação da pergunta da execução das consultas; sua disponibilidade deve ser confirmada no modelo local selecionado.

- No desenho proposto, uma pergunta será convertida em parâmetros validados, como período e categoria. Uma função autorizada consultará a base local e retornará o total e os lançamentos utilizados; a IA apresentará uma explicação. O modelo não receberá permissão para executar SQL arbitrário. Expressões ambíguas, como “mês passado” em um arquivo de período antigo, deverão ser confirmadas com o usuário quando o contexto não bastar.

### Decisão de Engenharia no Trokim
A conclusão desta pergunta norteadora estabelece que:
O chat começará por consultas de leitura e explicações acompanhadas do período analisado. Registros ou alterações sugeridos por conversa precisarão de confirmação e validação antes da gravação. O teste utilizará perguntas equivalentes, períodos ambíguos e pedidos sem dados suficientes. O sucesso será medido pela correção da consulta e da resposta, e não apenas pela naturalidade da conversa.

Esta decisão está formalizada no repositório através de: [ADR 0003](../adr/0003-rag-fontes-oficiais.md).

### Matriz de Decisão e Critérios do Sistema

| Recurso NLP | Objetivo no MVP | Salvaguarda de Segurança |
|---|---|---|
| **Consultas Conversacionais** | Permitir perguntas livres sobre despesas e conceitos regulados | RAG estrito com verificação de relevância |
| **Política de Abstenção Ativa** | Recusar respostas quando não houver evidência oficial comprovada | Threshold de similaridade semântica com recusa explícita |
| **Tool Calling / Estruturação** | Integração estruturada entre interface de chat e dados da API | Respostas com metadados de fonte e lista de evidências |

### Rastreabilidade
- **Requisitos Associados:** RF05, RF06
- **ADRs Vinculadas:** [ADR 0003](../adr/0003-rag-fontes-oficiais.md)

---

## GQ11 — Quais métricas podem avaliar a precisão das previsões e a eficácia das recomendações geradas pela IA?

> **Hipótese:** O projeto propõe analisar dados e considera modelos preditivos, mas a utilidade dessas técnicas depende de resultados verificáveis. Para esta pergunta, a hipótese derivada é que o sistema deve distinguir precisão de extração, classificação, cálculo, previsão e explicação. Não há uma única “acurácia da IA” que represente todas essas tarefas. O recorte técnico abaixo complementa os indicadores de compreensão, operação e valor apresentados na pergunta 4.

### Dados Encontrados e Fundamentação Científica
- O scikit-learn documenta MAE para erros absolutos, MAPE para erros relativos e F1 para classificação. O MAPE pode assumir valores muito elevados quando o valor real é próximo de zero. Por isso, a avaliação principal de despesas será o MAE em reais, acompanhado do tamanho da amostra e da comparação com uma estimativa simples.

- Na classificação de despesas, propõe-se reportar precisão, revocação e F1 por categoria e média macro, além da matriz de erros. Isso permitirá observar categorias pouco frequentes e distinguir erros de classificação de dados faltantes. Para as respostas, serão medidos acerto numérico, sustentação da afirmação pela fonte e reconhecimento de perguntas sem evidência. Repetições de uma mesma pergunta não deverão inflar a avaliação de generalização. === PAGE 28 ===

### Decisão de Engenharia no Trokim
A conclusão desta pergunta norteadora estabelece que:
O relatório deverá distinguir erros de importação, classificação, cálculo, previsão e explicação. Previsões só serão consideradas superiores à referência se melhorarem no mesmo conjunto de teste temporal; recomendações deverão respeitar as restrições e ser compreendidas pelo usuário. Valores ainda não medidos serão identificados como não avaliados, sem converter metas propostas em resultados.

Esta decisão está formalizada no repositório através de: [ADR 0004](../adr/0004-calculos-deterministicos.md).

### Matriz de Decisão e Critérios do Sistema

| Tarefa Técnica | Métrica Avaliada | Critério de Aceite |
|---|---|---|
| **Classificação por Categoria** | Macro F1 e F1-score por categoria (Scikit-Learn) | F1 >= 0.85 nas categorias essenciais |
| **Projeção Numérica em Reais** | Mean Absolute Error (MAE) comparado contra o baseline | MAE inferior ao desvio padrão histórico |
| **Explicação Textual** | Taxa de alinhamento com a fonte recuperada | Zero contradição factual com os textos do BCB/CVM |

### Rastreabilidade
- **Requisitos Associados:** RNF02, RF09
- **ADRs Vinculadas:** [ADR 0004](../adr/0004-calculos-deterministicos.md)

---

## GQ12 — Como as recomendações podem ajudar a equilibrar economia, lazer e necessidades básicas?

> **Hipótese:** A definição de qualidade de vida adotada considera que as prioridades variam entre pessoas e incluem aspectos além de produtividade ou dinheiro. A hipótese inicial derivada é que o assistente precisa considerar o que o usuário deseja preservar quando propõe ajustes. Lazer e necessidades básicas não serão tratados como categorias universalmente cortáveis; a pesquisa deverá verificar como negociar metas e limites sem produzir um plano incompatível com a rotina da pessoa.

### Dados Encontrados e Fundamentação Científica
- A CVM, em Planejamento e gestão de reservas financeiras, observa que destinar toda a sobra à poupança sem considerar qualidade de vida pode afetar a motivação de longo prazo. A página Momentos da vida também discute o equilíbrio entre despesas presentes e objetivos futuros. Essas referências apoiam cenários que preservem prioridades explícitas, sem uma regra única para todas as pessoas.

- Propõe-se que o Pierre pergunte quais despesas são indispensáveis e quais podem ser ajustadas. O usuário poderá comparar, por exemplo, uma contribuição mensal menor para uma meta com prazo maior ou uma redução escolhida em uma categoria ajustável. Quando não houver margem, o sistema explicará o conflito e permitirá rever a meta, sem sugerir que uma despesa essencial seja sacrificada automaticamente.

### Decisão de Engenharia no Trokim
A conclusão desta pergunta norteadora estabelece que:
As sugestões deverão apresentar efeitos e escolhas, permitindo preservar lazer e necessidades básicas dentro das restrições conhecidas. A validação verificará se o usuário reconhece suas prioridades no plano e consegue explicar o compromisso entre prazo, economia e gastos presentes. A sustentabilidade do comportamento dependerá de acompanhamento posterior, conforme a pergunta

Esta decisão está formalizada no repositório através de: [ADR 0004](../adr/0004-calculos-deterministicos.md).

### Matriz de Decisão e Critérios do Sistema

| Pilar Orçamentário | Tratamento no Sistema | Evidência Bibliográfica |
|---|---|---|
| **Necessidades Básicas** | Protegidas de corte arbitrário no simulador | Caderno de Cidadania do BCB (Despesas Fixas Essenciais) |
| **Lazer e Bem-Estar** | Reconhecido como componente essencial da saúde mental | [Portal do Investidor da CVM](https://www.gov.br/investidor/pt-br/investir/antes-de-investir) e Escala do CFPB |
| **Meta de Poupança** | Ajustada pelo usuário conforme a folga real do orçamento | Metas sustentáveis evitam desistência no médio prazo |

### Rastreabilidade
- **Requisitos Associados:** RF08, RNF01
- **ADRs Vinculadas:** [ADR 0004](../adr/0004-calculos-deterministicos.md)

---

## GQ13 — Como avaliar se o sistema contribui para melhorar o planejamento financeiro e a percepção de controle sobre o dinheiro?

> **Hipótese:** O problema de pesquisa combina desorganização das informações, incerteza sobre a fatura e desconforto com essa falta de clareza. A hipótese inicial é que consolidar e explicar os dados aumentará a percepção de controle. Isso precisa ser observado: uma interface considerada agradável não prova melhoria financeira. A avaliação proposta separará compreensão imediata, percepção relatada e mudanças que só podem aparecer ao longo do tempo.

### Dados Encontrados e Fundamentação Científica
- O guia da [Financial Well-Being Scale do CFPB](https://www.consumerfinance.gov/data-research/research-reports/financial-well-being-scale/) apresenta um instrumento para medir segurança e liberdade de escolha percebidas. A CVM relaciona organização financeira a objetivos e bem-estar. Esses materiais sustentam combinar indicadores objetivos de tarefa e relato do usuário; o uso de um questionário adaptado pelo projeto exige identificação própria, sem alegar validação equivalente ao instrumento original. === PAGE 29 ===

- Propõe-se um teste exploratório em que cada participante execute tarefas com o mesmo cenário antes e depois de receber apoio do Pierre. Serão registrados acertos, tempo, necessidade de ajuda e capacidade de justificar uma escolha. Perguntas curtas de compreensão e controle percebido complementarão o teste. A ordem das tarefas e a familiaridade prévia serão registradas para reconhecer possíveis efeitos de aprendizagem.

### Decisão de Engenharia no Trokim
A conclusão desta pergunta norteadora estabelece que:
Para o primeiro ciclo, a evidência esperada é demonstrar que o usuário entende melhor um cenário e consegue avaliar opções com apoio do assistente. A entrega distinguirá claramente protocolo, resultados de teste e limitações da amostra. A melhoria duradoura no planejamento e no bem-estar permanecerá como hipótese de pesquisa até que exista acompanhamento suficiente. Matriz de riscos e mitigação Privacidade e LGPD — evitar dados reais nos testes iniciais, minimizar coleta, revisar logs e conexões e definir responsabilidades [8, 9]. Erro de extração — comparar com gabarito, detectar duplicidades e submeter divergências à revisão humana [2]. Alucinações e recomendações inadequadas — cálculos determinísticos, RAG com fontes identificadas, indicação de limites e direito de recusa [5, 12]. Viés e diferentes situações financeiras — testes de renda variável, orçamento deficitário e dados incompletos, sem sugerir cortes universais [4, 8]. Viabilidade — começar por arquivos locais e medir usabilidade e desempenho antes de prometer escalabilidade [1, 6]. Métricas, validação e roadmap Importação correta = lançamentos com data, descrição e valor corretos / total esperado no gabarito. Acerto numérico = respostas com cálculo correto / perguntas numéricas avaliadas. Classificação = F1 macro e F1 por categoria [10]; previsão = MAE em reais comparado com baseline [11]. Fundamentação = respostas educacionais sustentadas por fonte identificada / respostas avaliadas. Utilidade = tarefas concluídas, tempo, necessidade de ajuda e justificativa da escolha; percepção declarada não comprova efeito causal [4]. Roadmap oficial [1]: semana 1 definições; 2 primeiro RAG; 3 comparação LLM x RAG; 4 primeiro sistema multiagentes; 5 multimodalidade; 6 integração; 7 avaliação final. Pendências: aprovação do escopo, responsáveis, dados sintéticos, desenho do piloto e metas quantitativas de aceite. Referências bibliográficas e documentação [1] Challenge 2 — Big Idea: Qualidade de Vida, slides oficiais da disciplina, 2026 (material fornecido). [2] Banco Central. Caderno de Educação Financeira. https://www.bcb.gov.br/pre/pef/port/caderno_cidadania_financeira.pdf

Esta decisão está formalizada no repositório através de: [ADR 0001](../adr/0001-flutter-android.md), [ADR 0003](../adr/0003-rag-fontes-oficiais.md).

### Matriz de Decisão e Critérios do Sistema

| Indicador de Utilidade | Método de Coleta | Significado para o Projeto |
|---|---|---|
| **Taxa de Conclusão de Tarefas** | Importar extrato, consultar saldo e simular cenário com sucesso | Usabilidade e clareza da interface Flutter no Android |
| **Tempo de Execução da Tarefa** | Cronometragem do fluxo antes e depois do apoio da IA | Redução de esforço e atrito cognitivo do usuário |
| **Controle Percebido (CFPB Adaptado)** | Questionário breve com base na [Financial Well-Being Scale do CFPB](https://www.consumerfinance.gov/data-research/research-reports/financial-well-being-scale/) | Indício exploratório de melhora na percepção de clareza |

### Rastreabilidade
- **Requisitos Associados:** RF07, RNF01
- **ADRs Vinculadas:** [ADR 0001](../adr/0001-flutter-android.md), [ADR 0003](../adr/0003-rag-fontes-oficiais.md)

---
