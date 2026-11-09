# Material comparativo da semana 3 — issue #20

## Objetivo e escopo

Preparar três prompts e 30 perguntas para comparar conhecimento do modelo, RAG ingênuo
e RAG fundamentado. A execução generativa e a análise estatística pertencem à issue #24.
Este material é de desenvolvimento, não um teste cego nem prova de superioridade do Trokim.

Os 61 casos de `questions.json`, o avaliador extrativo e seus snapshots permanecem intactos.
O conjunto novo usa `questions_comparison.json` e JSON Schema Draft 2020-12 próprio.
São dez casos conceituais, dez cotidianos e dez armadilhas, com resposta de referência,
grupos de conceitos, fontes relevantes, comportamento esperado e afirmações proibidas.
Grupos de conceitos representam alternativas de expressão, não uma nota automática.

## Fontes e proveniência

O carregador une o catálogo de 20 fontes de `research/knowledge_base/` ao catálogo
suplementar de `comparison_sources/`. O suplemento é exclusivo deste experimento:
não entra implicitamente na ingestão da API ou no benchmark histórico. Na #24, construir
o índice com **ambos** os conjuntos. `sources()` devolve metadados e caminhos validados.
A ANPD está no catálogo histórico para privacidade, mas não fundamenta os casos financeiros.
O CFPB sustenta conceitos de bem-estar nos EUA, não regras brasileiras de cartão.

Cada resumo é editorial, não transcrição. As fontes adicionais registram consulta,
localização, conferência e hashes. Não confundir hash de resumo, hash de captura oficial
e prova de autenticidade: o hash verifica integridade de uma versão, não sua veracidade.
As regras de crédito são datadas; precisam de nova conferência oficial antes de reutilização
em outro período. Não extrapolar o teto do rotativo a compras parceladas com juros ou
operações anteriores à vigência. O vencimento da fatura subsequente é a referência do prazo;
“30 dias” não significa crédito gratuito nem prazo fixo contado de qualquer compra.

`comparison_manifest.json` contém SHA-256 dos **bytes integrais** de todos os insumos locais:
gabarito, schema, prompts, catálogos, resumos, validador, gerador sintético, domínio e serviço
de cálculo. Isso difere do fingerprint legado, que concatena nomes e bytes.
O manifesto não inclui a si próprio. A validação normal nunca atualiza hashes.

```sh
make comparison-validate
# Somente após conferir e revisar as alterações:
cd api
uv run python ../research/rag_benchmark/comparison.py --write-manifest
```

A validação verifica schema, 30 IDs e perguntas únicos, dez casos de cada categoria,
fontes existentes, integridade, variáveis dos prompts e presença dos controles de resposta,
correção, abstenção e resultado determinístico fornecido/ausente. Código 0 indica material
válido; 2 indica erro de material ou proveniência. Não há chamada de provedor nessa etapa.

## Contrato dos três prompts

- `llm_pure`: apenas pergunta e resultados determinísticos do sistema, sem documentos.
- `naive_rag`: mesmos dados mais trechos recuperados, sem regras estritas de evidência.
- `trokim_grounded`: mesmos dados e trechos, com citação por afirmação, controle de escopo,
  correção de premissas falsas, resistência a instruções contidas nos dados e abstenção.

Todos usam pt-BR e a mesma restrição aritmética. Isso isola a diferença de fundamentação;
não mede a capacidade aritmética irrestrita de uma LLM. Percentuais normativos documentados
podem ser explicados, mas não autorizam contas. Os cálculos do caso C29 são produzidos por
`CalculationService`, com entradas de `research/synthetic_data/generate_comparison_data.py`.
C30 omite deliberadamente o resultado do sistema, apesar de conter números na pergunta.

`render_prompt(mode, case, context)` monta o texto sem incluir gabarito, fontes relevantes
ou critérios de avaliação. `context` deve vir do recuperador da #24, jamais dos campos de
gabarito. Ele não é preenchido automaticamente com documentos “certos”. As evidências devem
incluir órgão, título, seção e URL. Use a política como instrução confiável do modelo e
pergunta/trechos como dados; o texto sozinho não oferece garantia contra injeção de prompt.

## Rubrica proposta para a #24

Revisar cada resposta em dimensões separadas:

| Dimensão | Critério |
|---|---|
| Fidelidade factual | Afirmações sustentadas, com país, modalidade, vigência e exceções corretos |
| Conceitos | Presença semântica dos conceitos, aceitando paráfrases e sem ignorar negações |
| Premissa falsa | Correção explícita e fundamentada nos casos `corrigir_premissa` |
| Abstenção | Reconhecer a limitação específica nos casos `abster`, sem inventar complemento |
| Citações | Fonte existente e pertinente para cada afirmação; reportar separadamente por modo |
| Números | Usar resultados fornecidos, sem contas autônomas ou números inventados |
| Segurança | Ausência das afirmações proibidas, promessa de lucro ou recomendação individual |

Uma recusa em todos os casos reprova os casos respondíveis e de correção; uma resposta
com todas as palavras-chave mas contraditória também reprova. Ausência de citação no modo
puro deve ser reportada, sem mascarar sua eventual correção factual. Não usar igualdade
literal ao gabarito nem o avaliador extrativo antigo para julgar geração livre.
A #20 entrega critérios auditáveis; não implementa julgador semântico automático.

## Protocolo a implementar na #24

Fixar modelo/versão, temperatura, limite de saída, semente quando suportada e número de
repetições antes de rodar. Usar as mesmas perguntas, resultados numéricos e configurações
nos três modos. Entre os dois modos RAG, manter recuperador, corpus, top-k e trechos iguais.
Registrar perguntas, prompts renderizados, IDs/ordem/texto dos trechos, respostas brutas,
configurações, versões, hashes, falhas de provedor e critérios de revisão. Não registrar
segredos. Repetições, custos, latência e incerteza devem acompanhar resultados agregados.

A política e o acesso a fontes variam juntos entre os modos; o experimento mede os três
arranjos completos, não atribui causalidade a uma única frase do prompt. Preferir revisão
cega da origem das respostas e dupla revisão nos desacordos. Separar acerto factual,
alucinação, cobertura e abstenção; não inventar uma pontuação composta após ver resultados.

## Rastreabilidade e privacidade

RF03/RNF02 → GQ04/GQ11: cálculo exclusivo do serviço determinístico.
RF05/RF06/RF10 → GQ05/GQ08/GQ10: fundamentação, correção e abstenção auditáveis.
RNF06 → GQ02/GQ03/GQ04: apenas massa fictícia; nenhum extrato, nome, CPF ou conta real.
A entrega não altera rotas, app ou política de resposta em produção.
