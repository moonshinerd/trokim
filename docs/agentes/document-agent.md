# Agente de documento

Implementação da [#88](https://github.com/moonshinerd/trokim/issues/88), conforme o contrato
público do [épico #86](https://github.com/moonshinerd/trokim/issues/86).
Rastreabilidade: RF27, RF28; GQ02, GQ05; [ADR 0016](../adr/0016-arquitetura-multiagente.md).

!!! warning "Componente em implementação, sem integração HTTP"
    A leitura e a trilha têm testes determinísticos. As portas internas de OCR precisam ser
    adaptadas às portas definitivas da #87; os exemplos e a calibração dependem da #90.
    Não há motor OCR real configurado nesta entrega parcial. A API de extração, a validação
    financeira e a confirmação pertencem às #96 e #89. O recurso ainda não está disponível no app.

## Entrada, saída e responsabilidades

`DocumentAgent.run(DocumentContext)` devolve um `AgentStep` e coloca o `ExtractedDocument`
em `ctx.result`. O contexto tem `content: bytes` e `media_type` (JPEG, PNG ou PDF); os bytes
são excluídos de serialização e representação e a referência é apagada ao terminar, inclusive
em falha ou cancelamento. O chamador deve descartar suas próprias referências; isso não é uma
promessa de apagamento físico de memória do processo.

O agente não persiste lançamentos nem executa os agentes de pesquisa e comunicação do chat.
`AgentName.DOCUMENT` identifica seu passo; a integração ao fluxo HTTP fica na #96.
Um resultado bem-sucedido sempre tem `needs_review=True`.
Falhas técnicas devolvem passo `failed`, código seguro e `ctx.result=None`.

Os modelos de domínio ficam em `api/app/domain/documents.py`, com uma única definição do
contrato do épico. A #87 deve reutilizar esse módulo, evitando cópias concorrentes. As portas
`DocumentOcr`, `DocumentVision` e `VisionSanitizer` são internas e provisórias, sem fábrica ou
motor embutido. `TextReading.confidence` é a confiança agregada fornecida pelo adaptador de OCR;
`field_confidences` permite informar uma confiança específica por chave, que prevalece
sobre a média para aquele campo. O contrato definitivo deve ser alinhado às #87 e #89.

## Cobertura inicial e formatos

| Tipo | Layout | Campos esperados |
|---|---|---|
| Pix | Cabeçalho `Comprovante Pix` e linhas rotuladas | Data, valor, favorecido |
| Boleto | Cabeçalho `Boleto` e linhas rotuladas | Favorecido, valor, vencimento |
| Fatura sintética | Cabeçalho `Fatura de cartão` e linhas rotuladas | Banco, vencimento, total, lançamentos |
| PDF textual Ourocard/BB | Perfil existente `pdf_profiles.py` | Lançamentos e metadados explícitos |

Os três layouts rotulados são uma proposta verificável para os exemplos da #90, ainda não
uma cobertura validada de documentos de bancos reais. Datas rotuladas usam `DD/MM/AAAA`;
valores, o formato brasileiro com vírgula decimal. Campos duplicados e conflitantes não são
escolhidos por palpite. A mesma coleção detecta conflitos no perfil BB, nos layouts
rotulados e entre páginas ou motores; um campo removido por conflito não é reinserido
por uma leitura posterior. Todos os caminhos usam a mesma finalização de qualidade. Um lançamento sintético usa
`Lançamento: DD/MM/AAAA | descrição | 12,50`.

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

`image_quality.py` contém limites **provisórios, não calibrados**: lado mínimo 320 pixels,
variância do Laplaciano 15, desvio padrão de cinza 12 e confiança OCR mínima 0,80.
Esses números não demonstram precisão em fotografias reais e precisam ser calibrados na #90.
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

Saída de visão passa por esquema Pydantic com campos extras proibidos. JSON inválido ou falha
descarta a contribuição e preserva o OCR. A confiança autodeclarada nunca promove um novo campo
a seguro: propostas novas são normalizadas, sanitizadas e devolvidas com origem `vlm`,
confiança limitada a 0,50 e `VISION_REVIEW_REQUIRED`. São candidatas à revisão humana,
sem garantia de correção; tornam o resultado parcial. Divergências retiram o campo, sem
sobrescrita ou reinserção posterior. Campos desconhecidos, duplicados, datas/valores inválidos
ou formato inesperado descartam todo o lote antes de alterar o OCR. O motor `vlm` aparece
na trilha quando chamado. O limite de confiança ainda depende de alinhamento com a #89.

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
uv sync --extra documents
uv run pytest tests/test_document_agent.py
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

- Integrar as portas e o motor real da #87, sem duplicar contratos.
- Acordar os três layouts e calibrar os limites com os documentos da #90.
- Consolidar obrigatoriedade e confiança por campo com a #89.
- Documentar um ensaio reproduzível com OCR real: arquivos sintéticos, campos e limitações.
- Atualizar e verificar o lock de dependências, executar a suíte completa e o build estrito.

A meta de acerto de 90% pertence ao benchmark da #98; nenhum resultado novo de acurácia é
alegado por esta implementação parcial.


### Ajustes após revisão de código

Foram acrescentadas regressões para conflitos de total/vencimento do BB, preservação de
página BB legível em documento parcial, cabeçalho textual com recuperação por OCR,
confiança por campo, complemento de visão com baixa confiança, privacidade das propostas,
validação atômica de lotes de visão e linha de fatura sem data/valor. A leitura não afirma
completude quando uma linha reconhecida está incompleta.

Verificação local após os ajustes: 41 testes específicos do agente e 88 testes no conjunto
com parser, cálculos, análise, validação e orquestrador passaram. Ruff e formatação da API
passaram. Isso não substitui a suíte completa, o build estrito ou o ensaio com OCR real.

A atualização automática do `api/uv.lock` foi tentada, mas o ambiente de execução não
consegue resolver o endereço do PyPI. O lock ainda precisa ser regenerado com `uv lock`
antes de validar a instalação congelada do extra `documents`. Não é um check concluído.
