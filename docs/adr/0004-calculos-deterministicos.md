# 0004 — Separação entre Cálculos Determinísticos e Síntese de Linguagem

- **Status:** Aceita
- **Data:** 04/11/2026
- **Requisitos / GQs:** RF03, RF04, RNF02, GQ04

## Contexto
Modelos de linguagem generativa (LLMs) são excelentes para interpretar intenções, sintetizar textos e manter diálogos compreensíveis, mas são inerentemente probabilísticos e propensos a falhas aritméticas em somatórios extensos, cálculo de médias e projeções orçamentárias. No domínio financeiro pessoal, um erro de cálculo de R$ 50,00 ou uma inversão de sinal (despesa vs. receita) destrói completamente a credibilidade do aplicativo.

## Decisão
Estabelecer uma divisão estrita de responsabilidades:
1. **Cálculos Matemáticos Determinísticos:** Desenvolvidos inteiramente em código Python puro (`api/app/services/calculation_service.py`), garantindo 100% de precisão numérica, auditabilidade e cobertura por testes automatizados (pytest).
2. **Síntese e Diálogo com LLM:** A LLM recebe os valores numéricos já calculados de forma determinística como parâmetros de contexto e apenas gera a explicação em linguagem natural para o usuário, sendo expressamente proibida no system prompt de tentar recalcular ou inventar números.

## Alternativas Consideradas
- **Delegação Completa à LLM via Prompt Engineering:** Enviar todas as transações para a LLM somar no prompt. Descartada por comprovada vulnerabilidade a alucinações matemáticas e alto custo de tokens.
- **Python Code Interpreter / Tool Calling pela LLM:** Viável, porém adiciona latência, dependência de suporte a tool-use no modelo local e risco de segurança caso o código gerado seja executado sem sandbox.

## Consequências
- **Positivas:**
  - Garantia de 100% de precisão nos saldos, despesas e faturas.
  - Baixa latência e economia expressiva de chamadas de LLM.
- **Negativas / Riscos:**
  - Novas métricas de cálculo precisam ser programadas e expostas no serviço determinístico antes de poderem ser explicadas pelo assistente.
