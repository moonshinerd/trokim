# Ata de Reunião 01 — Alinhamento Inicial e Definição do Problema (Fase Engage)

* **Data:** 26 de outubro de 2026
* **Horário:** 15:20 às 17:00 (Gravações de áudio: partes 1 e 2)
* **Fase Metodológica (CBL):** Semana 1 – *Engage*
* **Big Idea:** *Qualidade de Vida*
* **Desafio Oficial:** *"Projetar e desenvolver uma solução baseada em IA capaz de apoiar a tomada de decisão em um contexto relacionado à qualidade de vida."*
* **Essential Question Formulada:** *"Como a inteligência artificial pode ajudar as pessoas a compreender e planejar suas finanças pessoais, tomando decisões informadas sem comprometer sua qualidade de vida?"*

---

## 1. Contexto e Abertura

A reunião teve como objetivo principal analisar o *briefing* do **Challenge 2 (Qualidade de Vida / TIC-IA 2026)**, compreender a abrangência da *Big Idea* e selecionar, por meio de deliberação coletiva, um problema concreto, relevante e tecnicamente viável para o desenvolvimento de uma solução orientada por inteligência artificial ao longo de 7 semanas.

O grupo debateu a premissa de que *qualidade de vida* é um conceito multidimensional — englobando saúde física, mental, social, relações interpessoais e estabilidade econômica —, sendo imperativo evitar soluções superficiais e focar em dores cotidianas reais que geram estresse e perda de controle.

---

## 2. Brainstorming Inicial e Alternativas Avaliadas

Durante a dinâmica de ideação, a equipe avaliou diferentes frentes temáticas antes de convergir para a proposta final:

| Proposta Levantada | Descrição e Hipótese | Motivo do Descarte / Redirecionamento |
|---|---|---|
| **Equilíbrio de Rotina Diária** | Aplicativo de cronograma pessoal customizável para conciliar alimentação, produtividade e lazer. | Escopo excessivamente amplo e disperso; baixa diferenciação de IA e risco de virar apenas mais um gerenciador de tarefas (*to-do list*). |
| **Filtro de Conteúdo em Redes Sociais** | Ferramenta para filtrar postagens tóxicas e limitar tempo de tela para combater a procrastinação. | Inviabilidade técnica de intervenção em APIs fechadas de terceiros (Instagram, TikTok) e risco de bloqueios de segurança do sistema operacional. |
| **Monitoramento e Higiene do Sono** | Assistente focado em regulação de hábitos noturnos e qualidade do descanso. | Dificuldade em formular um fluxo de IA claro sem a exigência de sensores adicionais de hardware (*wearables*). |
| **Assistente de Organização Financeira Pessoal** | Sistema inteligente para consolidar múltiplas contas e cartões, entender padrões de gastos e planejar o orçamento com IA. | **Ideia Eleita.** Dor aguda e universal vivenciada pelos próprios membros da equipe, com forte apelo em redução de ansiedade e alto potencial para aplicação de IA determinística e RAG. |

---

## 3. Aprofundamento do Problema Eleito: Descontrole Financeiro e Fragmentação de Contas

### 3.1 A Dor do Usuário
A equipe compartilhou relatos pessoais sobre o estresse decorrente da dispersão bancária:
- Grande parte das pessoas físicas utiliza múltiplos bancos (ex.: contas digitais como Nubank, bancos tradicionais) e diferentes cartões de crédito simultaneamente.
- A falta de visão integrada impede saber com precisão quanto já foi comprometido no mês: *"você passa o cartão sem saber quanto está a fatura e só descobre o estrago no final do mês"*.
- Essa opacidade gera ansiedade contínua, compromete a tomada de decisões e reduz a qualidade de vida do usuário.

### 3.2 O Papel da Inteligência Artificial
A equipe delimitou que a IA deve atuar como uma ferramenta de **clareza, categorização e apoio pedagógico**:
- Agrupar e distinguir despesas fixas (moradia, transporte) de gastos variáveis e supérfluos (lanches, assinaturas, compras por impulso).
- Identificar padrões de consumo ao longo do tempo.
- Prover modelos explicativos em linguagem acessível e permitir consultas em linguagem natural.

---

## 4. Discussão sobre Viabilidade Técnica e Arquitetura

Um dos pontos centrais da reunião foi a viabilidade da obtenção dos dados financeiros:

1. **Open Finance vs. Importação Manual de Arquivos:**
   - Foi levantada a hipótese de conexão direta via agregadores de Open Finance (ex.: Pluggy). Contudo, a equipe identificou que isso exigiria termos de uso comerciais, credenciais externas e cadastro de terceiros, gerando risco alto de atraso na entrega da Semana 1 e 2.
   - **Deliberação:** Adotar o processamento documental local a partir de arquivos padronizados exportados pelo próprio usuário (**extratos `.ofx` e faturas `.pdf`**), complementados por massas sintéticas nas semanas iniciais para blindar o projeto contra riscos de privacidade (LGPD).
2. **Cálculos Confiáveis vs. Alucinação de IA:**
   - Foi destacado que cálculos de saldo e totais não podem ser delegados a alucinações de modelos de linguagem, devendo ser estritamente determinísticos.

---

## 5. Estruturação Metodológica do CBL (Guiding Questions)

Para cumprir as diretrizes metodológicas da disciplina, a equipe combinou estruturar um documento compartilhado dedicado à investigação das **Guiding Questions (GQs)**.

Ficou estabelecido que cada pergunta norteadora deve ser formalmente documentada em três blocos obrigatórios:
1. **Hipótese Inicial:** A intuição e a suposição inicial da equipe diante da pergunta.
2. **Dados Encontrados e Fundamentação:** Evidências documentais e bibliográficas (órgãos reguladores como BCB, CVM, CFPB, normas da LGPD e literatura de IA).
3. **Hipótese Final / Reformulada:** A conclusão técnica adotada no projeto, indicando limites de escopo e critérios de aceite.

A equipe definiu como meta detalhar as 13 perguntas norteadoras cobrindo:
- Papel prático da IA e bem-estar financeiro;
- Riscos de privacidade e proteção de dados pessoais;
- Métricas objetivas de sistema (acurácia numérica, erro de previsão MAE, F1 de categorização);
- Base de conhecimento regulada e mecanismo RAG;
- Equilíbrio entre economia, necessidades básicas e lazer;
- Interface conversacional com saídas estruturadas.

---

## 6. Encaminhamentos e Tarefas Imediatas

- [x] Criação de documento compartilhado com o modelo das 13 Guiding Questions.
- [x] Divisão das perguntas norteadoras entre os membros do grupo para pesquisa de fundamentação.
- [x] Pesquisa das diretrizes do Banco Central do Brasil (Caderno de Cidadania) e CVM.
- [x] Consolidação da documentação viva em MkDocs/Zensical com as matrizes de risco e rastreabilidade.
