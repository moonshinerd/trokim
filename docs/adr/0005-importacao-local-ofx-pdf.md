# 0005 — Importação de Extratos Locais (OFX/PDF) em vez de Open Finance no MVP

- **Status:** Aceita
- **Data:** 04/11/2026
- **Requisitos / GQs:** RF01, RF02, RNF01, RNF06, GQ02, GQ03

## Contexto
O MVP do Trokim precisa atender pessoas que utilizam múltiplos bancos e cartões de crédito. Uma abordagem comum é a integração bancária direta via Open Finance utilizando plataformas de agregação de terceiros (ex.: Pluggy, Klavi). No entanto, tais integrações exigem aprovações regulatórias, credenciais comerciais pagas, compartilhamento de senhas/tokens em servidores de terceiros e suporte complexo a falhas de conexão bancária, o que consumiria a quase totalidade do cronograma das 7 semanas do CBL.

## Decisão
Restringir o canal de entrada do MVP à importação local de arquivos padronizados exportados pelo próprio usuário a partir dos aplicativos dos seus bancos:
1. **Extratos bancários em formato OFX (Open Financial Exchange):** Formato padrão da indústria suportado por praticamente todos os bancos brasileiros.
2. **Faturas de cartão em formato PDF:** Extração de texto e estruturação de lançamentos.
3. **Dados Sintéticos:** Criação de massa de dados sintéticos para testes e demonstrações sem risco de exposição de dados reais de integrantes da equipe ou participantes de testes.

A conexão direta via APIs do Open Finance fica catalogada como oportunidade futura para iterações pós-MVP.

## Alternativas Consideradas
- **Integração com Sandbox de Open Finance (ex.: Pluggy):** Exigiria autenticações externas e não funcionaria em modo estritamente local e desconectado.
- **Entrada Manual de Transação por Transação:** Causa extrema fricção e fadiga no usuário, desestimulando a continuidade do uso.

## Consequências
- **Positivas:**
  - Viabiliza a entrega tempestiva do roadmap (liberando tempo para RAG na Semana 2 e Multiagentes na Semana 4).
  - Controle absoluto do usuário sobre os arquivos fornecidos.
  - Testabilidade imediata via gabaritos sintéticos controlados.
- **Negativas / Riscos:**
  - O usuário precisa realizar o download manual do extrato/fatura em seu banco e carregar no aplicativo.
