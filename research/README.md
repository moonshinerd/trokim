# Pesquisa e avaliação RAG — issue #4

Base curada com **20 documentos-fonte distintos e 20 chunks** de BCB, CVM, CFPB
e ANPD. `knowledge_base/catalog.json` registra título, instituição, URL, localização,
data de consulta, resumo editorial e SHA-256 do arquivo local. O campo `verification`
registra um pequeno excerto de conferência e, para os 19 documentos lidos diretamente,
o SHA-256 do original. A página da Calculadora do Cidadão depende de JavaScript:
seu conteúdo foi conferido no índice de busca da página oficial, com essa limitação
explicitamente registrada, sem atribuir hash ao conteúdo não obtido.

Os TXT são **resumos editoriais**, não transcrições integrais, pareceres jurídicos ou
recomendações individuais. O material CFPB se refere ao contexto dos EUA. O guia ANPD
de poder público é usado para o princípio da necessidade, sem transportar as bases
legais específicas da administração pública para um aplicativo privado.

## Curadoria e rastreabilidade

O catálogo publicado está em `docs/rag/catalogo.md`. Para atualizar uma fonte:

1. Ler o original oficial, localizar a passagem e conferir o alcance da afirmação.
2. Redigir resumo temático, preservando fonte, título, URL, consulta e marcador de seção.
3. Registrar excerto curto, localização e hash original quando o conteúdo for obtido.
4. Atualizar `chunk_sha256` do TXT e o catálogo publicado.
5. Executar os testes e regenerar os relatórios. Não alterar o gabarito para esconder falhas.

Na revisão foram corrigidos o endereço antigo do Caderno BCB (agora apenas uma folha
com link para a versão atual), os links ANPD que apontavam à página de download e o
link de dívidas que retornava uma aplicação JavaScript sem o texto. Foram removidas
atribuições numéricas sem confirmação, como um tamanho universal da reserva de emergência.

## Chunking e representação

Cada arquivo contém um resumo temático autocontido; o parser extrai apenas o texto
após `[SEÇÃO 1: ...]`. Não há janela fixa nem sobreposição no baseline: fragmentar
resumos curtos prejudicaria a unidade conceitual. Título e seção entram na representação,
enquanto instituição, URL e cabeçalhos ficam como metadados de citação.

O índice esparso combina TF-IDF de palavras (1–2 gramas) e caracteres dentro de palavras
(3–5 gramas), com pesos iguais e similaridade cosseno. Usa normalização de acentos,
stopwords portuguesas de função, top-k=3 e limiar 0,15. Os caracteres ajudam com flexões
como investimento/investimentos. O índice é reconstruído em memória; não há persistência
vetorial nem embeddings neurais implementados nesta issue.

Para #8, a estratégia proposta é comparar recortes de originais de 256 e 512 tokens,
sobreposição de 10–20% e embeddings multilíngues locais, registrando modelo, versão,
dimensão, custo de memória e latência. Esses parâmetros são hipóteses de experimento,
não funcionalidades atuais. Usar o gabarito versionado e novos casos reservados para
avaliar o resultado sem otimização sobre as perguntas de teste.

## Execução e CI

Requer Python 3.12 e uv. Dependências de desenvolvimento incluem ReportLab para geração
do PDF. O lockfile é versionado.

```sh
make setup
make synthetic-data
make test
make lint
```

- `make test`: benchmark, testes de research e testes da API.
- `make research-test`: benchmark e testes de catálogo, gabarito e dados sintéticos.
- `make rag-eval`: relatório em `artifacts/research/current.json` (ignorado pelo Git).
- `make synthetic-data`: regenera os dois arquivos fictícios de novembro/2026.

O job `research` instala com `uv sync --frozen`, verifica lint/formatação, executa
`make research-test` e publica o relatório JSON como artefato inclusive quando as metas
falham. Os testes não usam rede, modelos externos ou dados reais.

Para reproduzir os snapshots versionados:

```sh
cd api
uv run python ../research/rag_benchmark/eval_rag.py --output ../research/rag_benchmark/results/current.json
uv run python ../research/rag_benchmark/eval_rag.py --retrieval-only --output ../research/rag_benchmark/results/baseline.json
```

O segundo comando retorna **1**, pois o controle sem política reprova a meta de abstenção.
Código 0 significa metas atingidas; 1 significa falha de métricas; 2 significa erro de
configuração/gabarito. Relatórios incluem casos, respostas, IDs recuperados, configuração,
versões e hashes do corpus, gabarito e serviço para identificar resultados desatualizados.

## Gabarito e métricas

São **61 casos**: 41 dentro do domínio (conceitos, situações cotidianas e uma pergunta
multifonte) e 20 de abstenção (incluindo sobreposição de termos financeiros, dados pessoais
indisponíveis, instruções adversariais e recomendações individuais). Cada pergunta tem
resposta de referência e grupos de conceitos aceitos. IDs relevantes são de chunks,
sem deduzir o acerto apenas pela instituição.

- **Recall@3:** média da fração de chunks relevantes recuperados entre os três primeiros.
- **Recuperação fundamentada:** proporção de perguntas no domínio cuja resposta cita como
  primeira evidência um chunk relevante, reproduz apenas o trecho do corpus com título e URL
  oficial, sem conselhos adicionais, e satisfaz os conceitos esperados. Só haver uma fonte correta em segundo lugar não basta.
- **Abstenção ativa:** proporção dos casos fora do escopo com `answered=false` e evidências vazias.

A execução reprova se recall ou recuperação forem menores que 90%, ou abstenção menor que
100%. Gabaritos vazios, sem uma das classes, duplicados e com IDs desconhecidos reprovam.
Testes negativos verificam que abster-se de tudo ou inventar uma resposta não passa.

| Controle no mesmo corpus e gabarito | Recall@3 | Recuperação fundamentada | Abstenção |
|---|---:|---:|---:|
| TF-IDF sem política de escopo | 95,12% | 97,56% (40/41) | 75% (15/20) |
| TF-IDF com política de escopo | 95,12% | 97,56% (40/41) | 100% (20/20) |

A falha **P12** (escolha de investimento para viagem em dois anos) está preservada. O
resultado comprova o ganho de 25 pontos percentuais da política de escopo neste conjunto.
Não demonstra superioridade contra uma LLM sem RAG: o controle é uma ablação do mesmo
recuperador. Uma comparação generativa exige definir modelo, prompts, execuções e rubrica
independente. Essa conclusão mais ampla não é inferida dos critérios de recuperação da #4.

O gabarito foi usado durante o desenvolvimento, inclusive na escolha da representação.
Não é um teste cego de generalização. A revisão corrigiu duas anotações incompletas: o
manual também responde ao número de itens da escala e a página da escala sustenta o
acompanhamento longitudinal. As fontes alternativas permanecem nos IDs relevantes e
contam no denominador de recall. Regras de escopo são conservadoras e não constituem
uma defesa geral contra prompt injection. A síntese atual é extrativa, sem LLM.

## Massa sintética e privacidade

O OFX usa banco de teste e conta `TESTE-SINTETICO-0001`, nomes fictícios e três
transações: crédito de R$ 5.000,00 e débitos de R$ 650,50 e R$ 1.500,00, saldo R$ 2.849,50.
A fatura PDF identificada como sintética contém três débitos que somam R$ 815,50, sem
nome, CPF, cartão ou conta de pessoa real. Os dados são fixos e o PDF usa modo determinístico.

Testes regeneram em diretório temporário, comparam OFX, texto do PDF e estabilidade de
geração, verificam datas, IDs, sinais e conciliação do saldo com Decimal. O PDF foi
renderizado e inspecionado visualmente. Os valores são massa de teste, não modelos de
fatura de uma instituição financeira.

## Requisitos

RF05/RF06: base oficial, referências e avaliação da recuperação. RNF06: massa fictícia,
minimização e testes sem dados financeiros reais. GQ05/GQ08/GQ11: fundamentação, limite
explicável de resposta e critérios de privacidade. Banco vetorial, ingestão completa e
síntese generativa continuam nas issues #8 e #3.
