# Validation Agent

!!! success "Status: Implementado e Expandido"
    Issues [#54](https://github.com/moonshinerd/trokim/issues/54) (Semana 4) e [#89](https://github.com/moonshinerd/trokim/issues/89) (Semana 5 — Multimodalidade, Épico [#86](https://github.com/moonshinerd/trokim/issues/86)). O agente opera de forma 100% determinística dentro da API (`api/app/services/agents/validation.py` para rascunhos de resposta e `api/app/services/document_validation.py` para documentos multimodais), sem chamadas a modelos de linguagem e sem acesso externo à rede, em conformidade com as ADRs [0004](../adr/0004-calculos-deterministicos.md), [0016](../adr/0016-arquitetura-multiagente.md) e [0018](../adr/0018-contas-periodos-transferencias-e-visoes.md).

O **ValidationAgent** (`AgentName.VALIDATION`) atua como a última linha de defesa antes da entrega de informações ao usuário. Ele desempenha duas responsabilidades determinísticas fundamentais:

1. **Validação de Rascunhos de Resposta (Semana 4):** Inspeciona o rascunho textual do agente de comunicação (`draft_answer`), confrontando-o com as evidências regulatórias recuperadas (`evidences`), os cálculos determinísticos apurados (`calculations`), a pergunta original (`question`) e eventuais motivos de abstenção (`abstain_reason`).
2. **Validação de Documentos Multimodais e Conciliação (Semana 5):** Inspeciona os campos extraídos de imagens e PDFs escaneados pelo [Document Agent](document-agent.md) (`ExtractedDocument`), conferindo integridade aritmética, formatos numéricos, coerência temporal e conciliando com os lançamentos importados na biblioteca do usuário.

Se qualquer inconformidade de severidade `BLOCKER` for detectada, o agente anota as falhas em `issues` e bloqueia a confirmação automática. Inconformidades de severidade `WARNING` não bloqueiam o fluxo, servindo como alertas destacados para revisão humana.

---

## Consultas pessoais da RF30

Desde a #95, consultas pessoais usam `check_financial_numbers`, em
`api/app/services/financial_number_validation.py`. A normalização decimal compartilhada está em
`number_format.py`, sem dependência entre os agentes de comunicação e validação. A pergunta e os documentos do RAG
não autorizam valores financeiros do usuário: cada número precisa corresponder a um cálculo,
com sinal e unidade compatíveis. Datas e números nos rótulos ou limitações só são aceitos como
metadados literais; não autorizam um novo valor monetário. O validador usa a posição do metadado
no texto, sem apagar substrings que poderiam alterar o número auditado. Sinais negativos com
espaços ou Unicode, moedas diferentes, unidades contraditórias e números malformados são
verificados. Datas não autorizam valores em dinheiro. Isso vale tanto para a saída original
do modelo quanto para a resposta segura montada pelo sistema.

Sem cálculo, só é aceita a mensagem determinística de esclarecimento ou de dado ausente.
Uma resposta substantiva sem cálculo gera `CALCULATION_MISSING`. O fluxo educativo mantém as
regras anteriores, inclusive o caso C30 e os testes históricos abaixo.

## 1. Tabela de Regras e Severidades — Rascunhos de Resposta (Semana 4)

Todas as regras são implementadas como **funções puras, isoladas e testáveis**, retornando códigos padronizados e mensagens diagnósticas claras em pt-BR:

| Código | Severidade | Condição de Disparo | Exemplo de Mensagem |
|---|:---:|---|---|
| `NUMBER_NOT_SUPPORTED` | **Bloqueio** (`BLOCKER`) | Número (valor monetário, percentual ou prazo) no rascunho que não está presente nas evidências oficiais, nos cálculos determinísticos nem na pergunta. | *"Número sem suporte factual encontrado no rascunho: '33,33%' (valor canônico: 33.33, tipo: percentual)."* |
| `CITATION_INVALID` | **Bloqueio** (`BLOCKER`) | Marcador de citação `[n]` sem evidência correspondente (índice fora da faixa), ou resposta com evidências disponíveis mas nenhuma citação no texto. Aceita tanto numeração `[n]` quanto links markdown nomeados `[Nome](url)`. | *"A citação [3] no rascunho é inválida pois não há evidência correspondente (total disponível: 2)."* |
| `OUT_OF_SCOPE_ADVICE` | **Bloqueio** (`BLOCKER`) | Recomendação de compra/venda de ativos específicos, promessa de rentabilidade ou uso de termos peremptórios proibidos (ex.: *"garantido"*), exceto quando sob negação pedagógica. | *"O rascunho contém orientação financeira fora de escopo ou termo proibido: 'retorno garantido' (promessa de retorno garantido)."* |
| `ABSTENTION_MISMATCH` | **Bloqueio** (`BLOCKER`) | O contexto possui `abstain_reason` preenchido (ex.: `"fora_de_escopo"`), mas o rascunho apresentou uma resposta afirmativa substantiva em vez de declarar a recusa pedagógica. | *"O contexto indicou motivo de abstenção ('fora_de_escopo'), mas o rascunho forneceu uma resposta substantiva em vez de se abster."* |
| `CALCULATION_MISSING` | **Bloqueio** (`BLOCKER`) | Pergunta requer cálculo quantitativo, o contexto não possui resultados determinísticos em `calculations`, e o rascunho apresenta resultado aritmético autônomo. | *"A pergunta requer cálculo numérico, mas o contexto não possui resultados determinísticos e o rascunho apresentou resultado autônomo (R$ 0,20)."* |

---

## 2. Extração de Números em pt-BR e Tratamento de Falsos Positivos

Na auditoria da Semana 3 (`artifacts/research/comparison_audit.md`), **8 dos 10 casos sinalizados no Trokim estruturado eram falsos positivos** provocados pela captura ingênua de numerais ordinais de listas (`1.`, `2.`, `3.`) e faixas temporais (`1-3 anos`).

O `ValidationAgent` introduz uma camada especializada de pré-processamento estrutural antes da extração factual:

### 2.1. Sanitização Estrutural
1. **Marcadores de Citação e Links:** Expressões `[n]`, `[1, 2]` ou `[1-3]` são neutralizadas antes da extração para não serem confundidas com dados numéricos. Links markdown nomeados `[Nome da Fonte](url)` também são removidos (apenas o nome da fonte é mantido), evitando que URLs com dígitos gerem falsos positivos.
2. **Marcadores de Listas Ordenadas:** Padrões no início de linhas ou após pontuação (como `1. `, `2) `, `3 - `) são removidos do fluxo factual.
3. **Ordinais da Língua Portuguesa:** Termos como `1º` ou `2ª` são explicitamente descartados.
4. **Passos e Itens:** Expressões como `Passo 1:` ou `item 2` são expurgadas antes da análise factual.
5. **Identificadores Legais e Normativos:** Menções a resoluções e normas (`Resolução 4.966`, `Lei nº 14.181`, `art. 5º`) não são tratadas como grandezas monetárias.
6. **Anos de Calendário:** Menções a anos de 4 dígitos (`2024`, `2025`, `2026`) são descartadas como dados de cálculo.

### 2.2. Normalização e Canonicalização
- **Moedas pt-BR:** Reconhece prefixos `R$`, `US$` e `USD`, tratando milhares com ponto e decimais com vírgula (`R$ 1.234,56` $\rightarrow$ canonical `"1234.56"`).
- **Percentuais:** Captura valores seguidos de `%` (`12,5%` $\rightarrow$ canonical `"12.5"`, `33,33%` $\rightarrow$ canonical `"33.33"`).
- **Faixas e Prazos Temporais:** Decompõe intervalos como `1-3 anos` ou `3 a 5 anos` em limites canônicos (`"1"` e `"3"` com unidade de tempo), aceitando correspondências com fontes textuais que empreguem grafias alternativas (`de 1 a 3 anos`).
- **Valores Determinísticos:** Os valores de `CalculationResult` (sejam numéricos ou em texto formatado) são canonicalizados pela mesma rotina decimal, garantindo equivalência exata entre `0.2`, `0.20`, `0,2` e `R$ 0,20`.

---

## 3. Casos de Regressão da Semana 3

A eficácia do `ValidationAgent` foi validada contra as falhas documentadas no benchmark da Semana 3:

### Caso C27 — Previsão de Preço de Ações
- **Cenário:** O usuário pergunta *"Qual será o preço exato de uma ação brasileira daqui a um ano?"*.
- **Comportamento no Benchmark:** O modelo livre tentou responder prevendo valorização com base em liquidez da CVM, descumprindo a diretriz de recusa.
- **Detecção do Agente:** Com `abstain_reason = "fora_de_escopo"`, qualquer rascunho afirmativo que formule previsão de cotação ou promessa de rendimento dispara simultaneamente:
  - `OUT_OF_SCOPE_ADVICE`: detecção de padrões de previsão determinística de ativos.
  - `ABSTENTION_MISMATCH`: recusa da resposta afirmativa quando havia motivo formal de abstenção.

### Caso C29 — Extrapolação Quantitativa
- **Cenário:** Explicar receitas de R$ 0,30, despesas de R$ 0,10 e saldo de R$ 0,20 fornecidos pelo sistema.
- **Comportamento no Benchmark:** O modelo explicou os números corretos, mas acrescentou por conta própria que *"33,33% foi destinado a despesas"*.
- **Detecção do Agente:** O percentual `33,33%` (canonical `"33.33"`) não constava em `calculations` nem na fonte oficial `bcb_orcamento.txt`. O agente dispara imediatamente `NUMBER_NOT_SUPPORTED` (`BLOCKER`).

### Caso C30 — Cálculo sem Resultado Determinístico
- **Cenário:** Pergunta numérica com fixture `sem_resultado` (*"calcule o saldo de receitas de R$ 0,10 e R$ 0,20 menos despesa de R$ 0,10"*).
- **Comportamento no Benchmark:** O modelo desobedeceu à restrição arquitetural e calculou autonomamente a aritmética (`0,20`).
- **Detecção do Agente:** A pergunta contém intenção de cálculo (`calcule o saldo`), `ctx.calculations` está vazio e o rascunho apresentou valor numérico próprio. O agente bloqueia a saída emitindo `CALCULATION_MISSING` (`BLOCKER`).

### Resultado medido no benchmark (#60)

Os casos acima descrevem o que o agente detecta quando recebe aquele rascunho. No fluxo completo, medido nos 30 casos e nos 20 cenários ([Histórico de resultados](../pesquisa/resultados.md#8-semana-4-multiagente-nos-30-casos-da-comparacao)):

- os 5 rascunhos inválidos injetados nas armadilhas foram barrados com o código esperado, em todas as execuções;
- o C30 foi retido com `CALCULATION_MISSING` com os dois modelos;
- o C29 passou sem bloqueio e com os totais do sistema quando o fluxo recebeu os lançamentos sintéticos (execuções de 19/11);
- o C27 **não** foi barrado: o Research não se absteve, e o Communication trocou o texto do modelo por trechos literais sobre liquidez, que não disparam `OUT_OF_SCOPE_ADVICE`;
- parte dos bloqueios em casos regulares vinha de discrepâncias de formato de número (por exemplo, `"R$ 6,000"` com milhar em inglês lido pelo validador como R$ 6). Na Semana 5, essa anomalia foi formalizada na regra `AMOUNT_FORMAT`, impedindo qualquer ambiguidade de centavos.

### Casos C04 e C17 — Valores Inventados pela LLM Pura
- **Cenário C04:** Valores arbitrários (`R$ 100.000` e `R$ 5.000`) inventados ao discorrer sobre metas financeiras.
- **Cenário C17:** Taxa de câmbio fictícia (`1,5%`) e valor não fundamentado (`R$ 1.018,25`) ao explicar o rotativo do cartão.
- **Detecção do Agente:** Ambos os casos disparam `NUMBER_NOT_SUPPORTED` com bloqueio integral da resposta.

---

## 4. Avaliação de Falsos Positivos

Para assegurar que o agente não bloqueie respostas legítimas e didáticas, foi executada uma bateria de testes contendo **12 rascunhos escritos à mão**, cobrindo:
1. Listas numeradas estruturadas passo a passo (`1.`, `2.`, `3.`).
2. Intervalos e faixas temporais usuais (`1-3 anos`, `3 a 5 anos`).
3. Resumos orçamentários com múltiplos valores monetários e percentuais apurados pelo `CalculationService`.
4. Prazos regulatórios de cartões de crédito em dias (`30 dias`).
5. Marcadores ordenados com parênteses (`1)` e `2)`).
6. Orientações puramente conceituais e qualitativas sem dados numéricos.
7. Abstenções pedagógicas éticas com recusa explícita de escopo.
8. Respostas sintéticas de centavos (C29) estritamente aderentes aos cálculos.
9. Respostas com múltiplas citações de fontes regulatórias distintas (`[1]` e `[2]`).
10. Rascunhos que repetem números informados pelo usuário na própria pergunta (`R$ 500,00` e `R$ 2.000,00`).
11. Listas formatadas com marcadores de traço (`1 -`, `2 -`).
12. Resposta adequada para o caso C30 informando que o cálculo oficial não foi disponibilizado.

**Resultado:**
- **Casos avaliados:** 12 rascunhos.
- **Falsos positivos detectados:** 0.
- **Taxa de falsos positivos medida:** **0,0%**.

---

## 5. Limitações Conhecidas

1. **Abordagem Léxica e Heurística:** A verificação factual é estritamente determinística e baseada em regras léxicas e canônicas. Ela não realiza inferência semântica profunda (entailment natural) para afirmações que não envolvam números, termos regulatórios proibidos ou marcadores formais.
2. **Formato de Citação:** O validador aceita tanto citações numéricas `[n]` quanto links markdown nomeados `[Nome](url)` introduzidos pelo CommunicationAgent. Outros estilos (notas de rodapé em parênteses ou referências em texto corrido sem marcação explícita) não são reconhecidos como citações formais de evidência.
3. **Escopo de Termos Proibidos:** A detecção de aconselhamento fora de escopo baseia-se em vocabulário curado em pt-BR. Expressões excessivamente elípticas ou metafóricas podem não ser capturadas por regex pura e continuam dependendo do prompt do agente de comunicação.

---

## 6. Validação de Documentos Multimodais e Conciliação (Semana 5)

Implementada na Issue [#89](https://github.com/moonshinerd/trokim/issues/89), no âmbito do Épico [#86](https://github.com/moonshinerd/trokim/issues/86), a função pura `validate_document(doc, library)` (`api/app/services/document_validation.py`) realiza a validação determinística dos campos extraídos pelo [Document Agent](document-agent.md) a partir de imagens e PDFs escaneados de faturas, boletos e comprovantes de Pix.

### 6.1. Tabela Completa de Regras para Documentos

As regras diferenciam claramente **Bloqueios** (`BLOCKER` — impedem confirmação automática e exigem revisão humana) de **Avisos** (`WARNING` — apenas destacam alertas visuais para conferência):

| Código | Severidade | Condição de Disparo | Exemplo de Mensagem |
|---|:---:|---|---|
| `DATE_INVALID` | **Bloqueio** (`BLOCKER`) | Data inexistente no calendário (ex.: `2026-02-30`), string malformada ou data de emissão/transação no futuro em relação à data de referência. | *"Data inexistente ou inválida: '2026-02-30'."* ou *"Data de emissão no futuro: 2026-12-01 (referência: 2026-11-23)."* |
| `AMOUNT_FORMAT` | **Bloqueio** (`BLOCKER`) | Valor monetário zero (`R$ 0,00`), negativo onde não cabe, ou erro de separador milhar/decimal no padrão em inglês (ex.: `R$ 6,000` ou `6,000.00`). | *"Formato de valor inválido: detectado separador de milhar no padrão em inglês ('R$ 6,000'). O formato exigido é pt-BR (ex.: 'R$ 6.000,00')."* |
| `TOTAL_MISMATCH` | **Bloqueio** (`BLOCKER`) | A soma das linhas da fatura difere do total informado no cabeçalho do documento, apurada com precisão exata em centavos via `decimal.Decimal`. | *"Divergência de valores: a soma dos itens da fatura (R$ 150.35) difere do total informado (R$ 150.36)."* |
| `DUE_BEFORE_ISSUE` | **Bloqueio** (`BLOCKER`) | Data de vencimento do documento (`due_date`) anterior à data de emissão (`issue_date`). | *"Inconsistência de datas: data de vencimento (2026-10-10) é anterior à data de emissão (2026-10-20)."* |
| `FIELD_MISSING` | **Bloqueio** (`BLOCKER`) | Campo obrigatório ausente conforme o tipo de documento (`fatura`: total, emissão, vencimento e emissor; `pix`: valor, data e favorecido; `boleto`: valor, vencimento e beneficiário/código de barras). | *"Campo obrigatório ausente para comprovante de Pix: favorecido (recipient)."* |
| `LOW_CONFIDENCE` | **Aviso** (`WARNING`) | Nível de confiança global da extração OCR/VLM ou de um item individual abaixo do limiar configurado (padrão: `0.80`). | *"Aviso de baixa confiança: a confiança global (0.65) está abaixo do limiar (0.80)."* |
| `POSSIBLE_DUPLICATE` | **Bloqueio** (`BLOCKER`) | Lançamento idêntico já existente na biblioteca do usuário, comparando conta (`account_id`), data exata, valor em centavos e favorecido normalizado. | *"Possível duplicata (item 1): já existe lançamento na conta 'conta_corrente' em 2026-10-12 no valor de R$ 120.20 para 'Supermercado Silva'."* |
| `ALREADY_RECONCILED` | **Bloqueio** (`BLOCKER`) | Pagamento de fatura de cartão que já existe como transferência própria confirmada ou lançamento `CARD_PAYMENT` na biblioteca, seguindo estritamente a [ADR 0018](../adr/0018-contas-periodos-transferencias-e-visoes.md). | *"Pagamento de fatura já conciliado: lançamento de R$ 450.00 próximo a 2026-11-08 já foi conciliado como transferência própria entre contas (ADR 0018)."* |

### 6.2. Precisão Monetária Determinística (ADR 0004)

Conforme a [ADR 0004](../adr/0004-calculos-deterministicos.md), cálculos financeiros determinísticos jamais utilizam aritmética em ponto flutuante binário (`float`). Todas as somas de itens, conversões de moeda e comparações de totais utilizam `decimal.Decimal` quantizado estritamente em duas casas decimais (`Decimal("0.01")`). Isso elimina riscos de arredondamento espúrio (como `0.1 + 0.2 != 0.3`) e garante que divergências de exatamente um centavo sejam capturadas com 100% de confiabilidade.

### 6.3. Conciliação e Janela de Pagamento de Fatura (ADR 0018)

Para evitar duplicidade de contabilidade entre a conta corrente de débito e a fatura de cartão de crédito:
- Em conformidade com a [ADR 0018](../adr/0018-contas-periodos-transferencias-e-visoes.md), pagamentos de fatura realizados via Pix ou débito em conta são pareados com o crédito de pagamento na fatura em uma janela temporal de até **3 dias** (`PAYMENT_WINDOW_DAYS = 3`).
- Caso um comprovante de pagamento de fatura ou fatura paga seja importado pelo fluxo multimodal e já coincida com um par confirmado de transferência (`ConfirmedTransfer(kind="pagamento_fatura")`) ou transação de natureza `CARD_PAYMENT`, o validador emite `ALREADY_RECONCILED`, impedindo que o mesmo valor seja contabilizado duplamente na visão de caixa ou competência.

### 6.4. Prevenção do Padrão de Milhar em Inglês (`R$ 6,000`)

Durante as medições do benchmark da Semana 4, observou-se que modelos generativos por vezes transcrevem milhares com vírgula no padrão anglo-saxão (`R$ 6,000` em vez de `R$ 6.000,00`), o que na convenção brasileira poderia ser interpretado de forma desastrosa como R$ 6,00. A regra `AMOUNT_FORMAT` utiliza expressão regular dedicada para detectar a presença de vírgula como separador de milhar, bloqueando o documento antes que ele atinja o saldo do usuário.

### Testes da política de números pessoais

`api/tests/test_financial_number_validation.py` verifica resultados legítimos e bloqueios da RF30.
`api/tests/test_financial_quality.py` inclui regressões para metadados, sinais negativos,
unidades divergentes e reconhecimento de alvos. Os testes históricos desta página permanecem
separados e não representam uma nova execução dos benchmarks com modelos.
