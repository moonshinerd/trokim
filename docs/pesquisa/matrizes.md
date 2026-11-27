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
| **Transcrição incorreta ou campo invisível inferido em imagem** | Alta | Alta | Comparador da #98 com campos exatos, campos não recuperáveis retornados, linhas e degradações separados; porteiro de qualidade, abstenção e revisão humana antes de importar. Acerto em números não equivale a documento integral correto. | GQ02, GQ05, RF27, RF28, ADR 0021 |
| **VLM remoto sem consentimento ou exposição de imagem** | Alta | Baixa | Leitura padrão só com OCR local; visão remota só com `allow_remote=true` enviado pelo app depois do consentimento do usuário (`403 REMOTE_CONSENT_REQUIRED` sem ele) e com CPF, CNPJ, agência e conta tarjados pelas caixas do OCR; benchmark remoto somente com os documentos sintéticos congelados e chave no ambiente. Leituras brutas do benchmark não autorizam retenção de documentos reais. | GQ03, RNF12, ADR 0021 |
| **Falha técnica confundida com recusa segura** | Alta | Média | Guardar trilha, falhas técnicas e latência por documento; indisponibilidade do túnel/modelo não conta como acerto nem abstenção correta. | GQ05, GQ10, RNF08 |
| **Escopo incorreto na resposta sobre contas e dívidas** | Alta | Média | Cenários isolados com filtros de conta, dono e período; gabarito do `CalculationService`, respostas brutas e bloqueios do Validation. Cálculo correto não garante reprodução correta pela LLM. | GQ04, GQ05, RF30, ADR 0023 |
| **Sobrecarga de escopo com Open Finance** | Alta | Alta | Descarte de integrações bancárias via Open Finance no MVP; foco exclusivo em arquivos exportáveis pelo usuário (OFX e faturas). | GQ02, ADR 0005 |
| **Viés contra rendas variáveis** | Média | Média | Cenários orçamentários flexíveis e personalizáveis, sem impor a regra 50-30-20 como padrão universal e sem assumir despesas supérfluas irreais. | GQ06 |

---

## Métricas Objetivas de Validação

Para avaliar empiricamente a eficácia da solução ao longo do roadmap:

1. **Taxa de Importação Correta:**
   `Taxa = lançamentos com data, descrição e valor idênticos ao gabarito ÷ total de lançamentos no gabarito sintético`
2. **Precisão Numérica Determinística:**
   Cálculos são determinísticos e confrontados com gabaritos nos testes. A reprodução dos valores na resposta da LLM é outra métrica: `valores esperados reproduzidos ÷ valores esperados`, acompanhada de números sem suporte e respostas retidas; não se presume acurácia de 100% do chat.
3. **Fundamentação do RAG:**
   `Taxa de fundamentação = respostas sustentadas por fonte oficial identificada ÷ total de respostas avaliadas`
4. **Taxa de Abstenção Correta:**
   `Abstenção correta = consultas sem evidência em que o modelo declarou ausência de dados ÷ total de consultas fora de escopo`
