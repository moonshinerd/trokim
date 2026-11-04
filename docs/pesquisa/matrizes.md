# Matrizes de Decisão e Gestão de Riscos

Matriz estruturada de riscos e medidas preventivas adotadas pelo projeto **Trokim**, em conformidade com as diretrizes do Challenge 2.

---

## Matriz de Riscos e Mitigação

| Risco Identificado | Severidade | Probabilidade | Estratégia de Mitigação | Rastreabilidade |
|---|---|---|---|---|
| **Vazamento de dados financeiros (LGPD)** | Alta | Baixa | Arquitetura local-first. Uso exclusivo de dados sintéticos em testes e desenvolvimento. Não persistência de dados sensíveis na nuvem. | GQ03, ADR 0002, ADR 0005 |
| **Alucinação em somatórios e saldos** | Alta | Alta | O motor de IA é proibido de realizar somas e subtrações; os cálculos são computados de forma determinística em Python antes da síntese. | GQ04, ADR 0004 |
| **Recomendações financeiras inadequadas** | Alta | Média | Base RAG restrita a órgãos oficiais (BCB, CVM, CFPB). Política explícita de abstenção quando a base não possuir evidência. | GQ01, GQ05, ADR 0003 |
| **Erros de parsing em extratos OFX/PDF** | Média | Alta | Validação por gabarito com dados sintéticos. Interface no app permitindo conferência e edição manual pelo usuário. | GQ02, GQ09 |
| **Sobrecarga de escopo com Open Finance** | Alta | Alta | Descarte de integrações bancárias via Open Finance no MVP; foco exclusivo em arquivos exportáveis pelo usuário (OFX e faturas). | GQ02, ADR 0005 |
| **Viés contra rendas variáveis** | Média | Média | Cenários orçamentários flexíveis e personalizáveis, sem impor a regra 50-30-20 como padrão universal e sem assumir despesas supérfluas irreais. | GQ06 |

---

## Métricas Objetivas de Validação

Para avaliar empiricamente a eficácia da solução ao longo do roadmap:

1. **Taxa de Importação Correta:**
   $$\text{Taxa} = \frac{\text{Lançamentos com data, descrição e valor idênticos ao gabarito}}{\text{Total de lançamentos no gabarito sintético}}$$
2. **Precisão Numérica Determinística:**
   $$\text{Acurácia Numérica} = 100\% \quad (\text{garantida por testes unitários com pytest})$$
3. **Fundamentação do RAG:**
   $$\text{Taxa de Fundamentação} = \frac{\text{Respostas sustentadas por fonte oficial identificada}}{\text{Total de respostas avaliadas}}$$
4. **Taxa de Abstenção Correta:**
   $$\text{Abstenção Correta} = \frac{\text{Consultas sem evidência onde o modelo declarou ausência de dados}}{\text{Total de consultas fora de escopo}}$$
