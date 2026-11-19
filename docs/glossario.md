# Glossário do Projeto

Terminologia técnica e conceitos de domínio adotados no **Trokim**.

---

## Conceitos de Finanças e Regulação

- **OFX (Open Financial Exchange):** Formato padronizado pela indústria financeira para intercâmbio eletrônico de extratos e lançamentos entre instituições bancárias e softwares de gestão.
- **Reserva de Emergência:** Montante correspondente a um período entre 3 e 6 meses do custo de vida essencial da família, aplicado em ativos de alta liquidez e baixo risco.
- **Despesas Fixas:** Gastos recorrentes e previsíveis cujo valor permanece substancialmente inalterado mês a mês (aluguel, condomínio, mensalidade).
- **Despesas Variáveis:** Gastos indispensáveis cujo valor flutua de acordo com a intensidade do consumo (água, luz, supermercado).
- **Despesas Supérfluas:** Gastos não essenciais vinculados a estilo de vida que podem ser reduzidos temporariamente diante de restrição orçamentária.
- **Bem-Estar Financeiro (CFPB):** Estado em que a pessoa tem controle sobre as finanças diárias, capacidade de absorver choques adversos, progresso em direção a metas e liberdade de fazer escolhas.

---

## Conceitos de Inteligência Artificial e Arquitetura

- **RAG (Retrieval-Augmented Generation):** Técnica que combina recuperação de trechos relevantes de uma base de conhecimento curada com um modelo de linguagem, condicionando a resposta à evidência factual recuperada.
- **Abstenção Ativa:** Comportamento intencional do sistema de declarar ausência de dados e recusar-se a responder quando a consulta não possuir respaldo documental confiável.
- **Cálculo Determinístico:** Processamento matemático estrito realizado por algoritmos imperativos (Python), garantindo exatidão aritmética sem intervenção de modelos probabilísticos.
- **Local-First:** Abordagem de engenharia em que os dados primários do usuário residem e são processados em seu próprio dispositivo, garantindo privacidade estrita e conformidade com a LGPD.
- **LLMProvider:** Porta (interface) que isola o restante do sistema do modelo de linguagem em uso. Tem adaptadores para LiteLLM, Ollama e um mock determinístico ([ADR 0009](adr/0009-sintese-generativa-local.md)).
- **LiteLLM:** Biblioteca que dá uma interface única a vários modelos. No Trokim é o provedor padrão, e o modelo é escolhido por configuração (`LLM_MODEL`).
- **Modos `grounded`, `naive` e `pure`:** Os três modos de síntese. `grounded` é o do produto (evidências oficiais, citação e abstenção); `naive` injeta trechos sem regras estritas; `pure` não usa documentos. Os dois últimos são bases de comparação.
- **F1 de tokens:** Sobreposição lexical entre a resposta e a resposta de referência. Mede palavras em comum, não fidelidade semântica.
- **Cobertura de conceitos:** Proporção dos conceitos obrigatórios do gabarito presentes na resposta.
- **Inconsistência factual (heurística):** Sinalização automática de número sem suporte na fonte, frase proibida ou negação contraditória. Gera falsos positivos e negativos e exige revisão humana.
- **Taxa auditada:** Proporção de casos com alucinação confirmada pela revisão manual. É a medida principal de alucinação, e um piso quando nem todos os casos foram revisados.
- **Execução (run):** Registro versionado de uma rodada do benchmark, com data, commit, modelo, parâmetros e métricas (`run.json`). Ver [Histórico de Resultados](pesquisa/resultados.md).
- **Agente:** Componente com um papel único no fluxo multiagente (Research, Analysis, Communication ou Validation). Recebe o contexto compartilhado, faz a sua parte e devolve um passo da trilha ([ADR 0016](adr/0016-arquitetura-multiagente.md)).
- **Orquestrador:** Código determinístico que chama os agentes em ordem, decide quando pular o Analysis, quando abster e quando pedir revisão, e monta a resposta final ([Orquestrador e Contratos](agentes/orquestrador.md)).
- **Trilha (dos agentes):** Lista de passos devolvida com cada resposta multiagente: agente, estado (`ok`, `skipped`, `abstained` ou `failed`), resumo e duração. O app a mostra em "Como cheguei a essa resposta".
- **Bloqueio (Validation):** Problema grave encontrado pelo Validation no rascunho (por exemplo `NUMBER_NOT_SUPPORTED`). Gera uma revisão do Communication; se persistir, a resposta é **rejeitada** e o rascunho fica retido.
- **Rejeição segura:** Desfecho `rejected` do fluxo multiagente: em vez do rascunho bloqueado, o usuário recebe uma mensagem fixa, sem conteúdo inventado.
- **Migração numerada:** Revisão do esquema do banco em `api/migrations/<banco>/versions/` (`001_...`, `002_...`), aplicada em ordem pelo Alembic ao abrir o banco ([ADR 0019](adr/0019-orm-e-migracoes-numeradas.md)).

---

## Conceitos de Extratos e Categorização

- **Natureza do lançamento:** Separa gasto real de movimentação de dinheiro (compra, Pix, pagamento de fatura, transferência própria, investimento) ([ADR 0017](adr/0017-perfis-de-banco-e-natureza-do-lancamento.md)).
- **CNAE:** Classificação Nacional de Atividades Econômicas (IBGE). Cada empresa tem uma atividade principal no cadastro do CNPJ; o Trokim converte essa atividade em categoria de gasto quando o extrato traz o CNPJ do recebedor ([ADR 0020](adr/0020-categorizacao-por-cnae.md)).
- **Índice CNPJ:** Arquivo local, gerado dos dados abertos da Receita Federal, que liga a raiz do CNPJ (8 dígitos) à categoria da atividade da empresa. Vai no repositório comprimido (14 MB) e é descomprimido localmente por `make build` ou pela API no primeiro uso; `make cnpj-atualizar` o refaz com um mês novo.
- **Dicionário de redes:** Nomes fantasia de empresas com muitos estabelecimentos ativos, com a categoria da atividade. Reconhece redes regionais pelo nome, mesmo sem CNPJ no extrato.
- **Conjunto de validação (holdout):** Casos rotulados escritos sem olhar as regras e sem ajuste depois da medição, para estimar o acerto da categorização em textos novos.

