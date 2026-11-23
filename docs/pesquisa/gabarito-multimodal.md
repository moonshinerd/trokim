# Gabarito multimodal sintético

O dataset da [#90](https://github.com/moonshinerd/trokim/issues/90) fornece documentos com
resposta conhecida para calibrar o [agente de documento](../agentes/document-agent.md) da
#88 e preparar o comparador de motores da #98. Rastreabilidade: RF14, RF27, RF28;
GQ02, GQ03, GQ05; [ADR 0008](../adr/0008-material-comparativo-versionado.md).

## Composição e construção

`research/synthetic_data/generate_document_images.py` usa Pillow, ReportLab, semente **90**
e a fonte redistribuível Bitstream Vera, incluída com sua licença em `fonts/`.
Não depende das fontes instaladas no sistema, da data atual nem de arquivos financeiros externos.
As versões de renderização estão fixadas em `api/uv.lock`; mudar essas versões pode mudar bytes.

| Propriedade | Composição |
|---|---|
| Arquivos | 40, em PNG, JPEG e PDF de imagem |
| Qualidade rotulada | 25 legíveis, 8 parciais, 7 ilegíveis |
| Tipos | Comprovante Pix, boleto e fatura de cartão |
| Bancos exibidos | Nubank, Nu Empresas, Banco do Brasil e Banco Horizonte Fictício |
| Famílias | 20 originais, cada um com uma variante |
| Calibração | 20 arquivos: 13 legíveis, 4 parciais, 3 ilegíveis |
| Verificação | 20 arquivos: 12 legíveis, 4 parciais, 4 ilegíveis |

As marcas são nomes públicos, sem reprodução de logotipos. São **layouts sintéticos rotulados**,
não réplicas certificadas dos aplicativos bancários. O documento traz aviso de demonstração;
nomes vêm de listas fechadas de exemplos, CPF repetido inválido, conta e agência zeradas.
Não há importação de imagem real, código de pagamento utilizável ou consulta à rede.

## Degradações e rótulos

Cada caso registra `degradation.type`, `level` e os parâmetros aplicados: desfoque gaussiano,
baixa iluminação, rotação, transformação de perspectiva, corte, JPEG de baixa qualidade ou reflexo
simulado por faixa branca que encobre texto. Os PDFs contêm somente imagem, sem texto selecionável;
o scan é uma representação raster, não outra classe de qualidade. Casos severos combinam
desfoque com iluminação variável; todos os sete ilegíveis têm nitidez abaixo do limite publicado.

O rótulo deriva da construção e da recuperabilidade dos campos, independentemente do resultado
do porteiro. Nos parciais, corte ou reflexo remove integralmente um campo essencial, mantendo os
demais: favorecido do Pix, vencimento do boleto ou total da fatura. Os ilegíveis não têm campos
marcados como recuperáveis. Esses rótulos são de desenvolvimento, sem revisão humana cega.

## Gabarito e integridade

`research/rag_benchmark/data/documents_gabarito.json` contém `id`, `family_id`, caminho, tipo,
banco, mídia, degradação, qualidade, conjunto e as marcações da demonstração. O schema ao lado
valida os tipos do contrato público do épico #86, datas, valores e campos obrigatórios por tipo.
Valores monetários de referência são strings decimais; o teste adapta linhas ao contrato
`ExtractedTransaction`, cuja saída pública usa `float`.

`expected_fields` e `expected_transactions` preservam o original. `recoverable_fields` e
`recoverable_transactions` indicam o que resta visível. Campo removido não é exigido do OCR;
se aparecer na saída, é contado separadamente como campo não recuperável retornado. Esse
indicador e linhas sem correspondência são diagnósticos automáticos, não revisão semântica.

`research/rag_benchmark/documents_manifest.json` registra SHA-256 dos bytes das imagens, PDFs,
gabarito, schema, gerador, fonte, licença e lock. Os testes verificam o manifesto sem atualizá-lo
e confrontam os arquivos versionados com uma nova geração. Antes de alterar hashes, revise a
mudança de insumo; regenerar o manifesto não justifica sozinho uma divergência inesperada.

## Reprodução

```bash
cd api
uv sync --frozen --extra documents
uv run python ../research/synthetic_data/generate_document_images.py
uv run pytest -c pyproject.toml ../research/test_document_dataset.py
cd ..
make docs-build
```

O gerador também aceita `--seed` e `--output <raiz>`, preservando os caminhos relativos. Use uma
pasta temporária para experimentar outra semente. A reprodução dos hashes usa a semente padrão,
a fonte versionada e as dependências do lock. Não substitua os dados oficiais por outra semente
durante uma execução comparativa.

## Calibração e ensaio com OCR real

```bash
cd api
uv sync --frozen --extra documents --extra ocr
uv run python ../research/rag_benchmark/calibrate_documents.py --ocr \
  --output ../research/rag_benchmark/results/documents/2026-11-23-rapidocr-v1
```

O destino precisa ser novo. `--ocr` exige RapidOCR real; não utiliza mocks nem transforma ausência
de motor em sucesso. Sem essa opção, mede apenas o porteiro. O CI do job `research` executa o
ensaio real e publica `run.json` e `readings.json` como artefatos, inclusive após falha.

O seletor avalia somente famílias da calibração, priorizando zero falso aceite de ilegíveis,
depois menor rejeição dos demais e, em empate, preservação das constantes. Os limites são
conferidos no conjunto de verificação sem reajuste. Variantes do mesmo original nunca atravessam
conjuntos. A busca inclui lado mínimo de 240/320/400 pixels, Laplaciano 5/10/15/25 e contraste
6/8/12; o candidato atual também entra explicitamente. Alteração selecionada exige publicação
no código antes de uma nova execução.

O relatório guarda commit, estado da árvore, hashes do código e manifesto, versões, parâmetros,
métricas por conjunto, leituras OCR, documentos devolvidos e trilhas. Apenas os bytes do arquivo
chegam ao agente: o gabarito é usado depois, no avaliador. O runner não possui VLM nem envio remoto.
A retenção de leituras brutas é restrita a este corpus fictício e não muda a política de privacidade
do agente no aplicativo.

As métricas incluem matriz de aceitação, acerto exato por campo recuperável, linhas exatas, correspondência de data/valor/parcela em
Decimal e contagem multiconjunto (sem reutilizar linhas), campos ausentes, incorretos ou
não recuperáveis retornados, divergências financeiras e de transcrição, abstenção segura e falhas
técnicas. O runner falha se houver falha técnica ou ilegível sem abstenção vazia. A confiança 0,80
permanece política conservadora, não probabilidade calibrada. Os resultados registrados estão no
[histórico](resultados.md#10-semana-5-calibracao-sintetica-do-porteiro).

## Exemplos e limites

`demo=true` identifica D01 e D03 (legíveis), D28 e D30 (ilegíveis).
`early_sample=true` acrescenta D12 parcial, formando os cinco exemplos iniciais da #88.
Os arquivos ficam em `research/synthetic_data/document_images/`.

O corpus tem margens, contrastes e layouts controlados; não representa a diversidade de
fotografias, câmeras, bancos ou documentos reais. Ruído e bordas podem ter Laplaciano alto sem
conter texto, e as métricas não comprovam corte ou reflexo. A exigência de todos os ilegíveis terem
baixa nitidez restringe a abrangência desses exemplos. Não há certificação de OCR em produção.
A comparação de três motores, a meta de 90% e os cenários de chat pertencem à #98, usando estes
insumos congelados. O [gabarito multiagente](gabarito-multiagente.md) continua independente.

Na revisão, o avaliador foi separado do runner em `document_evaluation.py`: funções puras
conferem cobertura e IDs únicos antes de contar resultados. Títulos OCR sem espaços são
reconhecidos pelo marcador conhecido; valores, favorecidos e descrições não são corrigidos
por heurística. Os casos da verificação já foram inspecionados nesta revisão: as novas
execuções são regressões de desenvolvimento, não uma estimativa de generalização em teste cego.
