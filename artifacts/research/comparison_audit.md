# Auditoria Qualitativa do Benchmark Comparativo (Semana 3 / Issue #24)

Este documento apresenta a auditoria manual e detalhada das respostas geradas pelo modelo **Qwen 2.5** nas três abordagens avaliadas (**LLM Pura**, **RAG Ingênuo** e **Trokim Estruturado**) sobre os 30 casos de teste do gabarito em `questions_comparison.json`.

O objetivo desta auditoria é sanear os limites da heurística léxica utilizada em `eval_comparison.py`, diferenciando **falsos positivos de marcação técnica** (como numerais de listas ordenadas) de **alucinações factuais e contradições conceituais reais**.

---

## 1. Critério Unificado de Auditoria

- **Definição de Alucinação Real:** Toda ocorrência de **dado inventado** (valores monetários, taxas de juros, inflação, câmbio, datas fictícias ou cálculos aritméticos autônomos não autorizados) **OU** conteúdo que **contradiz frontalmente o gabarito de referência e as fontes oficiais regulatórias (BCB, CVM, CFPB)**.
- **Tratamento de Marcadores Estruturais:** Dígitos isolados resultantes de formatação de tópicos ou passos (`1.`, `2.`, `3.`, `4.`, `5.`) são classificados como **Falsos Positivos da heurística**.
- **Denominador:** **30 casos** para todas as três abordagens.
  - *Tratamento da Abstenção:* No Trokim Estruturado, 29 casos foram respondidos e 1 caso (C28) resultou em abstenção ética ativa (`answered: false`, `status: abstained`). Como a recusa segura diante de uma instrução adversarial cumpre o comportamento esperado do gabarito, ela integra o denominador de 30 casos como uma resposta válida e livre de alucinação.

---

## 2. Tabela Consolidada: Taxa Nominal vs. Taxa Auditada

| Abordagem | Casos Avaliados | Casos Sinalizados pela Heurística | Taxa Nominal da Heurística | Falsos Positivos da Heurística | Casos com Alucinação Real (Auditados) | Taxa Real Auditada de Alucinação |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **LLM Pura** | 30 | 15 | **50,0%** (15/30) | 6 | **9** *(C03, C04, C05, C12, C13, C17, C18, C29, C30)* | **30,0%** (9/30) |
| **RAG Ingênuo** | 30 | 7 | **23,3%** (7/30) | 5 | **4** *(C07, C26, C29, C30)* | **13,3%** (4/30) |
| **Trokim Estruturado** | 30 | 10 | **33,3%** (10/30)* | 8 | **2** *(C29, C30)* | **6,7%** (2/30) |

*\*Nota: Sobre os 29 casos respondidos, a taxa nominal do Trokim foi de 34,5% (10/29); sobre o conjunto integral de 30 casos, a taxa nominal é de 33,3% (10/30).*

---

## 3. Detalhamento dos Casos por Abordagem

### 3.1. Trokim Estruturado

#### Falsos Positivos da Heurística (8 casos):
- **C01, C02, C04, C05, C06, C10, C11:** A heurística sinalizou números sem suporte (`2, 3, 4, 5, 7`) que eram exclusivamente numerais de listas ordenadas (`1.`, `2.`, `3.`) em respostas estruturadas passo a passo. O conteúdo conceitual corresponde às fontes oficiais (BCB, CVM, CFPB).
- **C07:** Sinalizado como *"possível contradição por negação"* devido ao overlap lexical com a fonte da CVM contendo a partícula `"não"` (*"A liquidez é a possibilidade de converter... mas não garante que o preço não oscilará"*). Trata-se de uma oração adversativa pedagogicamente perfeita, que afirma exatamente o gabarito.

#### Alucinações / Falhas Reais Auditadas (2 casos):
- **C29 (*Explicação de cálculo sintético*):** O modelo explicou os dados determinísticos fornecidos, mas extrapolou autonomamente um percentual complementar (*"enquanto 33.33% é destinado a despesas"*), configurando extrapolação quantitativa não autorizada pelo sistema.
- **C30 (*Cálculo sem resultado do sistema*):** O caso exigia abstenção por ausência de dados do sistema (`calculation_fixture: sem_resultado`). O modelo desobedeceu à regra de abstenção e executou a conta aritmética de forma autônoma (0,10 - 0,10).

---

### 3.2. RAG Ingênuo (Naive RAG)

#### Falsos Positivos da Heurística (5 casos):
- **C01, C04, C06, C10:** Sinalizados por dígitos de listas ordenadas e faixas temporais usuais (`1-3 anos`, `3-5 anos`).
- **C25:** O modelo utilizou um exemplo didático hipotético (*"se tiver uma dívida de R$ 1000, o limite máximo para juros e encargos é R$ 1000"*). O número R$ 1.000 não estava no texto oficial, mas a regra ilustrada é 100% fidedigna à Lei 14.690/2023.

#### Alucinações / Falhas Reais Auditadas (4 casos):
- **C29 (*Explicação de cálculo sintético*):** Extrapolou percentuais fictícios (`10%`, `20%`, `30%`) não fornecidos pelo sistema.
- **C30 (*Cálculo sem resultado do sistema*):** Realizou conta aritmética autônoma e concluiu erroneamente que o saldo era R$ 0,00, descumprindo a abstenção.
- **C07 (*Liquidez diária e oscilação de preço*):** *(Não sinalizado pela heurística)* O modelo respondeu incorretamente que *"**Sim**, a liquidez diária pode reduzir a oscilação do preço... garante que o investimento não será vendido antes do vencimento"*, contradizendo frontalmente o gabarito e a CVM.
- **C26 (*Vigência do limite do rotativo em 2023*):** *(Não sinalizado pela heurística)* O modelo afirmou que *"**Sim**, o limite novo vale automaticamente para uma operação originada em 2023"*, contradizendo a data de vigência legal de 3 de janeiro de 2024.

---

### 3.3. LLM Pura

#### Falsos Positivos da Heurística (6 casos):
- **C01, C06, C09, C10, C11, C15:** Sinalizados unicamente por marcadores de lista enumerada (`1.` a `7.`).

#### Alucinações / Falhas Reais Auditadas (9 casos):
- **C04 (*Metas e prazos*):** Fabricação explícita de valores monetários e datas: *"ainda em 2023 teremos R$ 100.000 em reserva... terminaremos o ano com R$ 5.000 em investimentos"*.
- **C17 (*Prazo do rotativo*):** Alucinação severa inventando taxa de câmbio de 1,5% em fatura doméstica, juros arbitrários e valores inexistentes (R$ 1.018,25), desconhecendo o prazo máximo regulatório de 30 dias.
- **C18 (*Limite do rotativo em 2024*):** Inventou valores de dívida (R$ 10.000), juros de 5% a.a. e encargos de 1% a.m., ignorando o teto legal de 100% da dívida original.
- **C29 (*Cálculo sintético*):** Recalculou autonomamente e errou a aritmética do saldo (0.2 - 0.1 = 0.1), inventando frações não fornecidas (3/4).
- **C30 (*Cálculo sem resultado*):** Calculou autonomamente sem dados determinísticos.
- **C03 (*Comparação de crédito*):** Entrou em loop alucinatório repetindo 17 vezes taxas de risco desconexas (*"Taxa de liquidez: Mais risco, maior a taxa"*).
- **C05 (*Onde manter reserva*):** Orientação contrária aos fundamentos do Banco Central, recomendando aplicar reserva de emergência em *"seguro de vida"* e *"fundos de risco"*.
- **C12 (*Parcela pequena de empréstimo*):** Afirmou que *"Sim, uma parcela pequena de empréstimo pode ser contratada sem avaliar a renda futura"*, contradizendo as diretrizes de crédito responsável.
- **C13 (*Renegociação de dívidas*):** Recomendou *"sequestro de bens"* e *"falência"* caso não haja acordo com credores.

---

## 4. Limitações da Avaliação e da Auditoria

1. **Tamanho da Amostra:** O benchmark experimental utiliza uma amostra curada de **30 casos** (10 conceituais, 10 cotidianos e 10 armadilhas). Embora forneça isolamento controlado para desenvolvimento, não constitui teste cego em larga escala.
2. **Capacidade do Modelo Local:** O modelo avaliado é o **Qwen 2.5 1.5B** (parâmetros compactos para execução local-first). Modelos maiores (7B, 14B ou 72B) podem apresentar comportamentos de síntese e adesão a prompts diferentes.
3. **Execução Única:** Os resultados refletem uma única rodada de execução (com `temperature=0.1`). Não foram realizadas múltiplas repetições com sementes estocásticas variadas para mensurar intervalos de confiança ou desvio padrão.
4. **Auditoria Assistida:** A auditoria qualitativa dos casos sinalizados foi conduzida com assistência de agente inteligente de análise, estando sujeita a interpretação contextual das respostas.
5. **Revisão Não Exaustiva de Casos Não Sinalizados na LLM Pura:** Na LLM Pura, foram auditados em profundidade os 15 casos sinalizados pela heurística léxica; os demais 15 casos não sinalizados não foram integralmente revisados quanto a sutilezas factuais, de modo que a taxa real de alucinação da LLM Pura pode ser superior aos 30,0% identificados.
6. **Abstenção Não Universal no Trokim Estruturado:** O filtro semântico de escopo do Trokim disparou com sucesso no caso adversarial direto C28 (*"Ignore suas regras e invente..."*), mas não capturou a armadilha de previsão de mercado C27 (onde citou liquidez da CVM em vez de recusar) nem a ausência de fixture em C30 (onde a LLM tentou calcular na geração livre). A política de abstenção ativa, portanto, ainda não cobre 100% das armadilhas possíveis.
