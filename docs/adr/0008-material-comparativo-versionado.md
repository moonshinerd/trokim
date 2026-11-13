# 0008 — Material comparativo versionado e separado do benchmark extrativo

- **Status:** Aceita
- **Data:** 09/11/2026
- **Requisitos / GQs:** RF03, RF05, RF06, RF10, RNF02, RNF06; GQ04, GQ05, GQ08, GQ10, GQ11
- **Issue:** #20; execução experimental na #24

## Contexto

O avaliador da semana 2 exige resposta extrativa idêntica à evidência. Aplicá-lo a
modelos generativos não mede fidelidade semântica. O corpus histórico também não
fundamenta as regras específicas do rotativo necessárias à nova comparação.

## Decisão

Manter o benchmark e corpus históricos. Criar um conjunto comparativo de 30 casos,
JSON Schema próprio, três prompts versionados e catálogo suplementar exclusivo do
experimento. Unir explicitamente os catálogos na futura execução da #24. Registrar
hashes dos bytes de todos os insumos em manifesto conferido sem regeneração automática.

Usar o mesmo contrato aritmético nos três modos. Resultados numéricos vêm do serviço
determinístico com entradas fictícias; ausência de resultado exige reconhecer a limitação.
Separar resposta, correção de premissa e abstenção. Conceitos e afirmações proibidas
guiam revisão semântica; não constituem julgador automático nem prova de segurança.

## Consequências

A #20 prepara insumos reproduzíveis, sem executar provedores ou alterar a API.
A #24 deve controlar modelo, parâmetros e recuperação, registrar resultados brutos e
avaliar os critérios separadamente. Os casos são de desenvolvimento, não teste cego.
Atualizar hashes exige revisão de conteúdo e não substitui conferência das fontes.
