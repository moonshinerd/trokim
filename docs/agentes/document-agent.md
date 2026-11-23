# Agente de documento

Implementação da [#88](https://github.com/moonshinerd/trokim/issues/88), conforme o contrato
público do [épico #86](https://github.com/moonshinerd/trokim/issues/86).
Rastreabilidade: RF27, RF28; GQ02, GQ05; [ADR 0016](../adr/0016-arquitetura-multiagente.md).

!!! warning "Componente integrado às portas, sem endpoint HTTP"
    O agente usa `OcrProvider`, `OcrResult`, `VisionProvider` e `VisionResult` da #87,
    já integrada à `main`. A fábrica seleciona OCR local e visão por configuração.
    O dataset da #90 já verifica os limites visuais em famílias separadas. O ensaio
    com OCR real tem runner próprio e execução configurada no CI; seus resultados devem ser
    registrados antes de concluir a #88. A validação financeira e a
    confirmação HTTP pertencem às #89 e #96. O recurso ainda não está disponível no app.

## Entrada, saída e responsabilidades

`DocumentAgent.run(DocumentContext)` devolve um `AgentStep` e coloca o `ExtractedDocument`
em `ctx.result`. O contexto tem `content: bytes` e `media_type` (JPEG, PNG ou PDF); os bytes
são excluídos de serialização e representação e a referência é apagada ao terminar, inclusive
em falha ou cancelamento. O chamador deve descartar suas próprias referências; isso não é uma
promessa de apagamento físico de memória do processo.

O agente não persiste lançamentos nem executa os agentes de pesquisa e comunicação do chat.
`AgentName.DOCUMENT` identifica seu passo; a integração ao fluxo HTTP fica na #96.
Um resultado bem-sucedido sempre tem `needs_review=True`.
Se nenhuma página produzir campos ou lançamentos, falhas técnicas devolvem passo `failed`,
código seguro e `ctx.result=None`. Havendo leitura segura em alguma página, o resultado é
parcial, preserva os dados e informa o código da falha operacional na trilha da página.

Os modelos de domínio ficam em `api/app/domain/documents.py`, com uma única definição do
contrato do épico #86. As portas e os resultados de leitura são importados diretamente de
`api/app/models/vision_provider.py` (ADR 0021), sem interfaces paralelas ou adaptadores fictícios.
`document_factory.get_document_agent()` usa as fábricas da #87 e `VISION_TIMEOUT`.

O OCR retorna `OcrResult.words` e `mean_confidence`; o agente agrupa palavras com caixas
sobrepostas na mesma linha e ordena as palavras por posição horizontal. Sem caixas, preserva
a ordem fornecida. A confiança do campo rotulado é o mínimo das palavras da linha e de suas
ocorrências repetidas; a média global é usada somente quando não há correspondência por chave.
Linhas de lançamento usam a confiança da própria linha; sem associação exata, usam
a menor confiança das palavras. Linhas abaixo do limite são descartadas com aviso,
mesmo que a média global seja alta. O limite de 0,80 é uma política conservadora compartilhada com a #89; não é uma probabilidade calibrada.

`VisionSanitizer` é um contrato interno de proteção dos pixels: não substitui `VisionProvider`.
Sem implementação que garanta anonimização, a visão continua bloqueada. A fábrica da #87
recusa visão remota sem consentimento; o agente também verifica essa autorização antes de
chamar um provedor remoto injetado diretamente.

## Cobertura inicial e formatos

| Tipo | Layout | Campos esperados |
|---|---|---|
| Pix | Cabeçalho `Comprovante Pix` e linhas rotuladas | Data, valor, favorecido |
| Boleto | Cabeçalho `Boleto` e linhas rotuladas | Favorecido, valor, vencimento |
| Fatura sintética | Cabeçalho `Fatura de cartão` e linhas rotuladas | Banco, vencimento, total, lançamentos |
| PDF textual Ourocard/BB | Perfil existente `pdf_profiles.py` | Lançamentos e metadados explícitos |

Os três layouts rotulados são exercitados pelo [dataset sintético da #90](../pesquisa/gabarito-multimodal.md),
sem certificar cobertura de documentos de bancos reais. Títulos e rótulos toleram ausência de
acentos, variação de caixa e espaços; isso não corrige valores ou nomes lidos pelo OCR. Datas rotuladas usam `DD/MM/AAAA`;
valores, o formato brasileiro com vírgula decimal. Campos duplicados e conflitantes não são
escolhidos por palpite. A mesma coleção detecta conflitos no perfil BB, nos layouts
rotulados e entre páginas ou motores; um campo removido por conflito não é reinserido
por uma leitura posterior. Todos os caminhos usam a mesma finalização de qualidade. Um lançamento sintético usa
`Lançamento: DD/MM/AAAA | descrição | 12,50`; também aceita a linha sem barras quando
a data e o valor brasileiro final são inequívocos. A confiança continua associada à própria linha.

Não há leitura genérica de qualquer layout, código de barras, QR Code ou autenticação bancária.
Não há correção de perspectiva, reflexo ou recuperação de fotos degradadas. A preparação
corrige orientação EXIF e converte imagens para RGB.

Limites internos: 20 MiB por arquivo, 10 páginas e 20 milhões de pixels por imagem renderizada.
A #96 deve aplicar limites HTTP iguais ou mais restritivos. Páginas são processadas em sequência;
a renderização PDF é serializada para não compartilhar chamadas concorrentes ao PDFium.

## Ordem e qualidade da leitura

1. Tenta a camada textual antes de qualquer métrica de imagem. Campos esperados e linhas
   completas permitem dispensar OCR e visão. Um cabeçalho selecionável ou um campo isolado
   não basta: páginas insuficientes passam pelo OCR, preservando os campos textuais seguros.
   Continuações BB reconhecidas podem conter apenas linhas de lançamentos.
2. Converte páginas sem texto útil em imagens, em memória, e avalia resolução, contraste e
   variância do Laplaciano.
3. Se a imagem passa pelo porteiro, chama OCR local e considera a confiança retornada.
4. A visão opcional só é considerada para campos ausentes ou incertos e com anonimização
   garantida por um adaptador explicitamente fornecido.

`image_quality.py` mantém lado mínimo 320 pixels, variância do Laplaciano 15 e desvio
padrão de cinza 12: os limites foram selecionados na calibração sintética da #90 e verificados
em famílias separadas. A confiança OCR mínima de 0,80 continua política conservadora.
Esses números não demonstram precisão em fotografias reais; a nitidez mede textura global,
não a presença de texto recuperável. Veja o [protocolo e as limitações](../pesquisa/gabarito-multimodal.md).
A confiança textual 0,95 é uma convenção inicial de extração, não probabilidade de correção.
Texto selecionável pode conter erros. A política definitiva por campo deve ser compartilhada
com a #89; o OCR usa a confiança por campo quando fornecida e a global somente como fallback.

| Situação | Resultado |
|---|---|
| Imagem rejeitada antes do OCR | Nenhum campo dessa página; motivo de qualidade |
| Confiança abaixo do limite | Descarta somente os campos de OCR incertos; preserva campos seguros das outras leituras |
| Alguns campos ausentes | Preserva os seguros; leitura parcial |
| Uma página ilegível | Preserva as demais; documento parcial e página indicada na trilha |
| Todas as páginas ilegíveis | `abstained=True`, sem campos/lançamentos; pede nova foto |
| Legível, sem campo seguro | Abstenção distinta de ilegibilidade |
| Layout desconhecido | Aviso `UNSUPPORTED_LAYOUT`; não inventa campos |
| Divergência entre páginas | Remove o campo divergente; `FIELD_CONFLICT` |

O relatório público possui métricas da primeira página avaliada e qualidade global conservadora;
a trilha indica as páginas não lidas. Em PDF textual, resolução `(0, 0)` e nitidez `0` significam
**não aplicável**; não são evidência de imagem ruim. O contrato não tem coordenadas ou origem por
página em cada campo. Contraste é medido internamente, sem ampliar o contrato.
Avisos não atribuem corte de texto sem evidência: as métricas não comprovam essa causa.

## Privacidade e visão opcional

Arquivos, páginas, texto OCR e respostas brutas do modelo não são gravados em disco ou log pelo
agente. Nome do favorecido e banco podem permanecer para revisão. Textos livres removem linhas
com CPF/CNPJ/conta/agência e sequências numéricas; valores e datas têm formatos estritos.
A sanitização textual é conservadora e pode retirar números legítimos de descrições.

A trilha contém apenas motor, duração, número de campos, códigos e situação por página.
Não inclui nome do arquivo, imagem, base64, prompt, texto bruto ou exceção do fornecedor.

Nenhum anonimizador universal de pixels é entregue. Sem um `VisionSanitizer` que garanta a
proteção da imagem, `VISION_PRIVACY_BLOCKED` impede a chamada. Uma implementação que apenas
retorna os bytes originais só é admissível em testes com imagem sintética sem dados pessoais.
O consentimento remoto deve ser aplicado pela fábrica da #87, além dessa proteção.

O JSON em `VisionResult.content` passa por esquema Pydantic com campos extras proibidos. JSON inválido ou falha
descarta a contribuição e preserva o OCR. A confiança autodeclarada nunca promove um novo campo
a seguro: propostas novas são normalizadas, sanitizadas e devolvidas com origem `vlm`,
confiança limitada a 0,50 e `VISION_REVIEW_REQUIRED`. São candidatas à revisão humana,
sem garantia de correção; tornam o resultado parcial. Divergências retiram o campo, sem
sobrescrita ou reinserção posterior. Campos desconhecidos, duplicados, datas/valores inválidos
ou formato inesperado descartam todo o lote antes de alterar o OCR. O motor `vlm` aparece
na trilha quando chamado; o OCR informa o identificador de `OcrResult.engine`. O limite de 0,50 da visão permanece apenas candidato para revisão; a #89 aplica a validação financeira.

## Valores, falhas e validação

Valores de campos gerais são strings decimais normalizadas. Lançamentos seguem o contrato
existente (`float | None`); só convertem formatos inequívocos, usando `Decimal` antes da saída.
Datas ou valores ambíguos permanecem ausentes. A #89 decide obrigatoriedade, somas, duplicatas
e bloqueios financeiros; o agente só sinaliza incompletude e problemas de leitura.

Falhas técnicas não são ilegibilidade. Entre os códigos seguros estão `INVALID_IMAGE`,
`INVALID_PDF`, `PASSWORD_PROTECTED`, `FILE_LIMIT`, `PAGE_LIMIT`, `PIXEL_LIMIT`,
`PDF_RENDERER_UNAVAILABLE`, `OCR_UNAVAILABLE`, `OCR_TIMEOUT` e `INVALID_OCR_RESULT`.
A #96 definirá os códigos HTTP correspondentes. Cancelamento é propagado após a limpeza.

## Verificação e pendências de conclusão

```bash
cd api
uv lock --check
uv sync --frozen --extra documents
uv run pytest tests/test_document_agent.py tests/test_document_providers.py tests/test_vision_ports.py
uv run ruff check .
uv run ruff format --check .
cd ..
make docs-build
```

O extra `documents` declara Pillow e pypdfium2; OCR e modelo não são exigidos pelo teste
unitário. Os testes cobrem leitura simulada, PDF textual (incluindo perfil BB), página ilegível,
conflitos, privacidade, limites, falhas, cancelamento e esquema de visão inválido.
As imagens aleatórias dos testes exercitam as métricas e não representam um benchmark de OCR.

Antes de considerar a #88 concluída:

- Verificar o ensaio real e registrar os resultados do runner da #90.
- Manter a política compartilhada: Pix exige data/valor/favorecido; boleto exige
  favorecido/valor/vencimento; fatura exige banco/vencimento/total e ao menos uma linha completa.
  OCR abaixo de 0,80 é descartado com aviso; visão fica limitada a 0,50 e exige revisão.
  A #89 continua responsável por bloqueios financeiros, somas e conciliação.
- Conferir CI verde e a integração da PR #108 à main antes do fechamento por PR complementar.

A meta de acerto de 90% pertence ao benchmark da #98; nenhum resultado novo de acurácia é
alegado por esta implementação parcial.


### Ajustes após revisão de código

Foram acrescentadas regressões para conflitos de total/vencimento do BB, preservação de
página BB legível em documento parcial, cabeçalho textual com recuperação por OCR,
confiança por campo, complemento de visão com baixa confiança, privacidade das propostas,
validação atômica de lotes de visão e linha de fatura sem data/valor. A leitura não afirma
completude quando uma linha reconhecida está incompleta.

A integração acrescenta testes com `MockOcrProvider` e `MockVisionProvider` públicos,
reconstrução de linhas por caixas OCR, confiança por campo, bloqueio de consentimento remoto,
fábrica configurável e renderização real de PDF em memória. O lock combina os extras `ocr`
e `documents`; `uv lock --check --offline` valida o conjunto sem alterar dependências.

Verificação local: 498 testes de API e 161 de pesquisa passaram. Dois testes de OCR real
da #87 e um teste opcional de pesquisa foram pulados por dependências/recursos ausentes.
Essa é a validação histórica da PR #108. A #90 acrescenta corpus, testes de reprodução,
calibração separada por família e runner com OCR real; o histórico de resultados distingue
a medição visual de uma execução de extração.
