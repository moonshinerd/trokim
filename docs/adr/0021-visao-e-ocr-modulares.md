# 0021 — Leitura de imagem modular: portas de OCR e de visão

- **Status:** Aceita
- **Data:** 23/11/2026
- **Requisitos / GQs:** RF27, RF28, RNF01, RNF10, RNF12; GQ01, GQ02, GQ03
- **Issues:** [#87](https://github.com/moonshinerd/trokim/issues/87), [#91](https://github.com/moonshinerd/trokim/issues/91)
- **ADRs relacionadas:** [0009](0009-sintese-generativa-local.md), [0015](0015-dados-reais-importacao-e-endereco-da-api.md), [0016](0016-arquitetura-multiagente.md)

## Contexto

A Semana 5 pede um agente multimodal: ler foto ou PDF escaneado de fatura, comprovante de Pix e
boleto. Os motores de leitura de imagem mudam depressa e têm custos diferentes de qualidade,
latência e privacidade. Imagem de documento financeiro é dado pessoal: enviá-la a um serviço de
nuvem contraria a premissa local-first do projeto.

## Decisão

1. **Duas portas**, no padrão do `LLMProvider` ([ADR 0009](0009-sintese-generativa-local.md)), em
   `app/models/vision_provider.py`: `OcrProvider.read(imagem) -> OcrResult` (palavras com
   confiança e caixa) e `VisionProvider.extract(imagem, instruções, esquema) -> VisionResult`
   (JSON como texto, validado depois pelo agente de documento). Trocar de motor é configuração.
2. **OCR local por padrão.** `RapidOcrProvider` (RapidOCR sobre ONNX, a mesma pilha do FastEmbed)
   roda no próprio aparelho do usuário e não precisa de internet. É um extra opcional
   (`uv sync --extra ocr`); o CI usa o `mock`.
3. **Modelo de visão opcional e desligado** (`VISION_PROVIDER=none`). Quando ligado, passa pela
   camada LiteLLM, o mesmo ponto de configuração do texto: `ollama/qwen2.5vl` (local) ou
   `openrouter/...` (remoto), só mudando `VISION_MODEL`.
4. **Consentimento para provedor remoto.** A fábrica trata como remoto qualquer modelo que não
   seja Ollama, ou cujo endereço não seja a própria máquina (`localhost`, `127.0.0.1` e
   `host.docker.internal`). Um modelo remoto **só é aceito com `VISION_ALLOW_REMOTE=true`**
   (padrão `false`); sem isso a fábrica recusa com `RemoteVisionNotAllowedError`. A nuvem só
   recebe material sintético no benchmark.
5. **Privacidade.** A imagem fica só em memória durante a chamada. Nenhum adaptador registra a
   imagem, o texto lido ou o JSON devolvido, e a mensagem de erro do modelo de visão não inclui o
   conteúdo enviado. Chaves vêm só de variável de ambiente.
6. **Backend em contêiner.** `deploy/Dockerfile` empacota a API com o OCR e o modelo de
   embeddings já baixado, e roda como usuário sem privilégios. O app Flutter fica fora do
   contêiner, instalado no aparelho.
7. **Revisão humana no app.** No app Flutter (`mobile/lib/features/documents/`), a leitura é assistida:
   o usuário visualiza uma prévia antes da leitura, vê cada campo extraído com seu nível de confiança
   (alta, média, baixa), edita dados duvidosos, resolve bloqueios e confirma ou descarta explicitamente.
   Linhas podem ser excluídas e bloqueios só são liberados quando os campos obrigatórios correspondentes
   são alterados para valores válidos; campos opcionais não bloqueiam. Bloqueios sem campo editável
   continuam impedindo confirmar. Imagens ilegíveis orientam nova tentativa com dicas de enquadramento. Nenhum
   lançamento é criado sem confirmação humana ativa. A etapa inicial utiliza repositório de teste
   (mock) e a integração com o endpoint real pertence à issue #97.

## Consequências

- O agente de documento ([#88](https://github.com/moonshinerd/trokim/issues/88)) depende só das
  portas e é testável sem OCR nem modelo, com os mocks.
- Um motor melhor, local ou remoto, entra como um adaptador novo, sem mexer no agente.
- O OCR traz o OpenCV e o ONNX Runtime (cerca de 150 MB no ambiente); por isso é um extra
  opcional e a imagem Docker é grande.
- A confiança do OCR alimenta o porteiro de qualidade da imagem, que decide abster-se quando a
  foto não permite concluir.
- A tela de revisão do app desacopla o motor de extração da confirmação do usuário; trocas de motor
  ou modelos não alteram o fluxo de conferência nem criam lançamentos de forma silenciosa.

## Alternativas descartadas

- **Um único modelo de visão:** lento no hardware da equipe e impreciso em números; o OCR lê o
  texto de forma barata e o modelo de visão só complementa.
- **OCR em nuvem:** envia a imagem de um documento financeiro a terceiros.
- **Tesseract:** exige binário do sistema e vai bem pior em foto com perspectiva; fica como
  adaptador futuro caso o RapidOCR não atenda.
