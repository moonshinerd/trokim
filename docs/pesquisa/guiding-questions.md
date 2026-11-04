# Perguntas Norteadoras (Guiding Questions)

As Guiding Questions orientam as investigações do projeto Trokim, formalizando as hipóteses, evidências bibliográficas e conclusões técnicas preliminares.

---

### GQ01 — Papel da IA no Empoderamento Financeiro
- **Questão:** Como a inteligência artificial atuará de forma prática para empoderar o usuário a "compreender melhor, decidir melhor e viver melhor" sua rotina financeira?
- **Hipótese Inicial:** Reunir informações dispersas e explicá-las com IA aumentaria a clareza sobre entradas, saídas e gastos recorrentes, reduzindo o estresse financeiro.
- **Evidências:** O Caderno de Cidadania Financeira do BCB e materiais da CVM apontam que o orçamento serve para avaliação de prioridades. O CFPB define bem-estar financeiro pelo controle cotidiano e liberdade de escolha.
- **Conclusão:** A IA atua como interface explicativa e de apoio à decisão, sem tomar decisões de gastos pelo usuário e sem realizar pagamentos no MVP.

### GQ02 — Delimitação de Escopo e Fontes de Dados
- **Questão:** Como delimitar o escopo de entrada de dados para garantir a entrega tempestiva do roadmap (RAG na semana 2, multiagentes na semana 4 e multimodalidade na semana 5)?
- **Hipótese Inicial:** Integração com Open Finance via provedores externos (ex.: Pluggy).
- **Evidências:** Conexões com agregadores externos geram risco de dependência de credenciais, termos de serviço e atrito de autenticação.
- **Conclusão:** O MVP focará em importação local de arquivos padronizados (OFX e PDF), com dados sintéticos nas primeiras semanas para eliminar riscos de privacidade.

### GQ03 — Mitigação de Riscos de Privacidade e LGPD
- **Questão:** Quais medidas de segurança e conformidade são necessárias para lidar com arquivos bancários pessoais?
- **Hipótese Inicial:** Armazenamento em nuvem com criptografia de ponta a ponta.
- **Evidências:** A LGPD (Lei 13.709/2018) e resoluções da ANPD exigem minimização de dados e finalidade estrita.
- **Conclusão:** Arquitetura *local-first*. Nenhum extrato bancário do usuário é enviado para treinamento de modelos públicos; todo o banco transacional opera localmente no SQLite.

### GQ04 — Prevenção de Alucinações em Cálculos Numéricos
- **Questão:** Como garantir que a IA não invente valores numéricos ou forneça cálculos incorretos de balanço?
- **Hipótese Inicial:** Utilizar prompts solicitando que o modelo "seja muito preciso nas contas".
- **Evidências:** Estudos de LLM comprovam que modelos autoregressivos frequentemente cometem erros aritméticos ao somar longas listas de transações.
- **Conclusão:** Separação estrita de papéis: código determinístico calcula saldos, totais e percentuais; a LLM apenas recebe esses dados já calculados para formular a resposta explicativa.

### GQ05 — Fundamentação e Abstenção via RAG
- **Questão:** Como certificar que recomendações de corte de gastos ou reserva de emergência tenham respaldo técnico?
- **Hipótese Inicial:** Permitir que o modelo utilize seu conhecimento pré-treinado geral sobre investimentos.
- **Evidências:** O relatório do CFPB sobre *Chatbots in Consumer Finance* aponta risco de viés e conselhos inadequados.
- **Conclusão:** Implementação de RAG estrito baseado nos guias oficiais do BCB, CVM e CFPB. Se a base de conhecimento não contiver a resposta, o sistema declara explicitamente que não possui evidências suficientes.

### GQ06 — Tratamento de Desigualdade e Rendas Variáveis
- **Questão:** Como evitar que o sistema presuma que todas as pessoas possuem salário fixo ou despesas supérfluas fáceis de cortar?
- **Hipótese Inicial:** Aplicar a regra tradicional "50-30-20" como padrão obrigatório.
- **Evidências:** Grande parcela da população brasileira possui renda flutuante ou orçamento deficitário estrutural.
- **Conclusão:** O sistema não assume que gastos essenciais possam ser cortados arbitrariamente; as simulações de orçamento oferecem alternativas ajustadas pelo próprio usuário.

### GQ07 — Experiência do Usuário no Android
- **Questão:** Qual arquitetura de aplicativo móvel proporciona maior clareza visual e menor carga cognitiva para o usuário?
- **Hipótese Inicial:** Telas densas repletas de gráficos e tabelas detalhadas.
- **Evidências:** Interfaces com sobrecarga informativa reduzem o engajamento de usuários com baixa literacia financeira.
- **Conclusão:** Flutter com telas modulares: visão consolidada rápida (dashboard), histórico pesquisável, importador de arquivos com feedback visual e chat consultivo.

### GQ08 — Auditoria e Rastreabilidade de Decisões
- **Questão:** Como auditar as recomendações feitas pelo assistente ao usuário?
- **Hipótese Inicial:** Armazenar apenas o histórico de mensagens de chat.
- **Evidências:** Para garantir transparência, é necessário saber qual trecho da fonte regulatória foi injetado no prompt.
- **Conclusão:** Todo atendimento registra os metadados da consulta RAG (ID do chunk, fonte, relevância e prompt utilizado).

### GQ09 — Métricas de Avaliação Empírica
- **Questão:** Quais métricas quantitativas atestam a qualidade do sistema nas entregas semanais?
- **Hipótese Inicial:** Avaliação qualitativa de satisfação subjetiva.
- **Evidências:** O projeto exige métricas objetivas: taxa de acerto na importação de lançamentos (OFX/PDF), acurácia de cálculos numéricos, revocação e precisão do RAG.
- **Conclusão:** Definição de baselines sintéticos contra gabaritos conhecidos em `research/rag_benchmark/`.

### GQ10 — Evolução Multiagente e Multimodal
- **Questão:** Como preparar a base de código na Semana 2 para suportar os módulos das Semanas 4 (Multiagentes) e 5 (Multimodalidade)?
- **Hipótese Inicial:** Monólito procedural direto no router.
- **Evidências:** O acoplamento precoce inviabiliza orquestração de múltiplos agentes especializados.
- **Conclusão:** Arquitetura limpa com portas e serviços isolados (`api/app/services/`), permitindo plugar agentes especializados e visão computacional futuramente sem quebrar o core.
