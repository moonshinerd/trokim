# Trokim — Aplicativo Mobile (Flutter)

Módulo cliente Android do projeto Trokim, desenvolvido em Flutter (Dart).

---

## Estrutura do App

```text
mobile/
├── pubspec.yaml              # Dependências do Flutter
├── lib/
│   ├── main.dart             # Inicialização e barra de navegação
│   ├── core/
│   │   ├── constants/        # URLs da API e constantes
│   │   ├── network/          # Cliente HTTP REST
│   │   ├── settings/         # Preferências locais (SettingsController/Scope)
│   │   ├── sharing/          # Arquivo recebido por "Compartilhar" (canal com o MainActivity)
│   │   ├── theme/            # Design System: paleta, claro/escuro, AppColors
│   │   └── widgets/          # Moeda 3D, mascote, movimento e cabeçalhos
│   └── features/
│       ├── dashboard/        # Resumo calculado pela API (receitas, despesas, poupança e categorias)
│       ├── transactions/     # Importação por seletor de arquivos e lista de extratos OFX/PDF
│       ├── finance/          # Modelos, repositório e controlador do resumo e da importação
│       ├── chat_assistant/   # Chat com resposta fundamentada, fontes clicáveis e histórico de conversas
│       ├── agents/           # Contratos Dart estritos para resposta e trilha multiagente
│       ├── import_guide/     # Fluxo guiado de importação (banco, dono, tipo, tutoriais, detector e resumo)
│       ├── categories/       # Revisão das categorias dos gastos (regra por estabelecimento)
│       ├── transfers/        # Transferências entre contas próprias (sugestões, confirmar, desfazer)
│       ├── installments/     # Parcelamentos e projeção mensal
│       ├── budget_scenarios/ # Simulador e comparador de cenários
│       └── settings/         # Aba Ajustes: tema, animações, modo multiagente, endereço da API e conexão
├── assets/
│   ├── brand/                # Arte do mascote (ver LEIA-ME.md, licença CC0)
│   └── fonts/                # Plus Jakarta Sans (OFL)
```

---

## Execução

Requer Flutter **3.50.0** (mesma versão do CI) e, para gerar o APK, JDK 17 e Android SDK 36 (ver
[Validação local](#validacao-local)). Se o Flutter não estiver no `PATH`, use o
caminho completo do executável nos comandos abaixo.

### Backend local

Na raiz do repositório, em um terminal separado:

```bash
make setup
make api-run
```

Antes de iniciar a API, disponibilize o modelo local em outro terminal:

```bash
ollama serve
```

Com o servidor Ollama ativo, prepare o modelo uma vez:

```bash
ollama pull qwen2.5
```

O download inicial do modelo exige internet. Durante a demonstração, configure
`LLM_PROVIDER=ollama`, `LLM_MODEL=qwen2.5` e
`LLM_API_BASE=http://localhost:11434` no ambiente do backend. O timeout padrão do
modelo é `LLM_TIMEOUT=60` segundos. Prepare também o corpus/embeddings locais
conforme as instruções da API antes da demonstração.

A tela usa `POST /v1/chat/generate`, enviando `message` e `mode: grounded`.
O aplicativo recebe `query`, `answered`, `status`, `mode`, `answer`, `model` e
`evidences`. Modos experimentais e respostas incompatíveis são rejeitados com
mensagem amigável, sem fallback para `/ask`. O endpoint extrativo permanece
disponível na API, mas não é usado pelo fluxo normal do chat.

As evidências preservam instituição, título, seção, trecho, relevância e URL;
`document_id` e `source_url` podem estar ausentes ou nulos no cliente.

O modo **Multiagente (experimental)** fica em Ajustes, desligado por padrão e
salvo no aparelho. Ligado, o chat usa `POST /v1/agents/ask`; cada resposta traz
trilha tipada dos agentes, duração, cálculos e validações. O botão **Como
cheguei a essa resposta** abre as etapas e explica abstenções/rejeições em
linguagem simples. Desligado, o fluxo configurado de chat continua igual.

### Importação guiada (Nubank)

**Extratos → Importar extrato** abre `features/import_guide/`: escolha do banco, tipo (fatura do
cartão ou extrato da conta), tutorial passo a passo e resumo. Em toda tela há **Pular tutorial**,
e **Já tenho o arquivo** vai direto ao seletor. **Não mostrar este tutorial de novo** (e o
interruptor **Tutorial ao importar extratos** em Ajustes) controla `showImportTutorial`, salvo no
aparelho; desligado, o app abre o seletor na hora. O resumo mostra o banco detectado pela API,
lançamentos lidos, repetidos ignorados, movimentações fora dos totais e gastos sem categoria. O
Resumo ganha **Onde você mais gastou**, calculado pela API. Testes:
`test/import_flow_test.dart` e `test/nubank_summary_test.dart`.

### Várias contas, Banco do Brasil e categorias (ADR 0018)

- **Bancos e donos:** Nubank (pessoal e Empresas) e Banco do Brasil (fatura Ourocard em PDF e
  conta em OFX), cada um com seu tutorial. Antes de importar, o app pede à API a análise do
  arquivo (`/transactions/inspect`) e só pergunta o dono ou mostra um aviso quando é preciso.
- **Situação do período:** o resumo da importação mostra se a fatura está aberta ou fechada (ou o
  extrato parcial) e permite confirmar ou configurar o período; em Extratos, cada arquivo tem a
  situação e uma folha para ajustá-la, além de avisos de lacunas e a lista de contas com dono
  editável.
- **Transferências e parcelamentos:** telas próprias, abertas pelos atalhos de Extratos e pelo
  resumo da importação. O Resumo filtra por dono (Tudo, Pessoal, Empresas), alterna Gastos e
  Caixa e mostra o total por conta.
- **Categorias:** tocar numa categoria do Resumo, ou em **Categorizar agora** no resumo da
  importação, abre `features/categories/`. A escolha vale para o estabelecimento todo e para os
  próximos arquivos (a API guarda a regra).
- **Compartilhar:** no Android, OFX e PDF enviados por "Compartilhar" ou "Abrir com" abrem o
  fluxo com o arquivo já escolhido (`MainActivity.kt` e `lib/core/sharing/`).

Testes: `test/import_flow_contas_test.dart`, `test/library_screens_test.dart`,
`test/category_review_test.dart` e `test/shared_file_test.dart`.

### Timeout da geração

A geração tem prazo próprio de **90 segundos**, independente dos 15 segundos
usados pelas demais chamadas. O prazo inclui recuperação, geração e comunicação;
ajuste-o ao equipamento e mantenha margem sobre `LLM_TIMEOUT` do backend:

```bash
flutter run --dart-define=CHAT_GENERATE_TIMEOUT_SECONDS=120
```

Use um valor inteiro positivo em segundos. Assim como `API_BASE_URL`, essa
configuração é definida na compilação e exige reiniciar a execução do app.

O prazo é aplicado ao transporte HTTP completo, inclusive à leitura do corpo.
Ao expirar, o cliente aborta a requisição e só devolve o erro quando o transporte
confirma o cancelamento. Fechar o cliente também aborta gerações pendentes.
A API monitora a desconexão, cancela a operação associada e aguarda sua limpeza;
o cliente HTTP do provedor local é encerrado durante esse cancelamento.
Isso não constitui confirmação de que o Ollama já interrompeu seu processamento
interno: esse comportamento precisa ser conferido no ambiente de demonstração.

### Emulador Android

Com o emulador iniciado, na pasta `mobile/`:

```bash
flutter pub get
flutter run
```

O endereço padrão é `http://10.0.2.2:8000/v1`: `10.0.2.2` aponta para o host no
emulador Android padrão. A plataforma Android inclui permissão de internet e
tráfego HTTP habilitado para esse backend local. Essa configuração de transporte
é para desenvolvimento; um serviço remoto de produção deve usar HTTPS.

### Celular físico

Conecte o celular e o computador à mesma rede confiável. Como `make api-run`
escuta apenas em `127.0.0.1`, para permitir acesso pela rede inicie o backend
com o comando abaixo, em vez de manter os dois servidores na mesma porta:

```bash
cd api
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Na pasta `mobile/`, substitua `<ip>` pelo endereço local do computador e execute:

```bash
flutter run --dart-define=API_BASE_URL=http://<ip>:8000/v1
```

Autorize a porta 8000 no firewall somente na rede confiável, se necessário.
`API_BASE_URL` é definido na compilação; mudar o endereço exige executar o app
novamente com o parâmetro, não apenas hot reload. O mesmo parâmetro permite usar
uma porta diferente se 8000 estiver ocupada.

## Chat e tratamento de falhas

A funcionalidade separa modelos em `domain/`, acesso à API em `data/` e estado/
interface em `presentation/`. O controlador mantém o histórico durante a sessão,
impede envios simultâneos e preserva as boas-vindas. Mensagens podem ter até 1000
caracteres. Respostas fundamentadas exibem cartões expansíveis com instituição,
título, relevância, trecho recuperado e link para o documento oficial. O controle
**Auditoria** mostra a origem da resposta com RAG e explica por que não apresenta
uma resposta alternativa sem evidências. Abstenções aparecem com aviso e perguntas
rápidas para temas permitidos, sem cartões de evidência. Falha de conexão, timeout
da geração ou erro HTTP geram mensagem amigável e a ação **Tentar novamente**,
que repete a última pergunta com erro sem duplicar seu balão.

O histórico existe apenas na sessão visual: cada requisição envia a pergunta
atual, sem mensagens anteriores, extratos ou saldos. O modelo não realiza os
cálculos financeiros. A resposta é exibida integralmente após a geração, sem
streaming. `grounded` indica uso de evidências recuperadas, sem certificar cada
afirmação ou citação. Abrir um link oficial no navegador é um acesso externo
voluntário, separado do processamento local da pergunta.

Para demonstrar no emulador, inicie Ollama e a API e rode `flutter run`; pergunte, por
exemplo, **Como montar uma reserva de emergência?**. Ative **Auditoria** e expanda
um cartão para conferir a seção original e abrir a fonte oficial.

Para o roteiro de homologação e o registro das verificações desta integração,
consulte [Validação do chat generativo](VALIDACAO_CHAT_GENERATIVO.md).

## Verificações no CI

O job **mobile (análise + testes)** usa Flutter 3.50.0, instala as dependências
com `--enforce-lockfile` e executa a checagem de formatação, `flutter analyze` e
`flutter test`. A versão efetivamente instalada aparece no log do job. Esse job
não substitui a homologação com Android e Ollama reais.

## Validação local

Na pasta `mobile/`:

```bash
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
flutter build apk --debug
```

Os testes usam `MockClient`, sem backend ativo nem rede. Cobrem conversão de
respostas, metadados opcionais, erros HTTP/conexão/timeout, concorrência e ciclo
de vida do controlador, cartões expansíveis, abertura de URL, comparação de
auditoria, abstenção, perguntas rápidas, carregamento e nova tentativa.
O fluxo multiagente também cobre resposta aprovada, abstenção, rejeição,
payload inválido, falha de rede, exibição da trilha e persistência do
interruptor em Ajustes.
Testes e análise podem ser executados sem instalar plataformas ou aceitar
licenças do SDK. O build do APK exige:

- JDK 17 (`flutter config --jdk-dir <caminho>`);
- Android SDK com `platforms;android-36`, `build-tools;36.0.0` e
  `ndk;28.2.13676358`, com licenças aceitas (`flutter doctor --android-licenses`);
- acesso a `dl.google.com` e ao Maven Central na primeira execução, para o Gradle
  baixar as dependências (as execuções seguintes usam o cache).

Sem Android Studio, basta instalar as command-line tools em uma pasta do usuário
e apontar o Flutter com `flutter config --android-sdk <caminho>`. O APK de debug
fica em `build/app/outputs/flutter-apk/app-debug.apk`.

Não versionar `build/`, `.dart_tool/`, `android/local.properties` ou demais
artefatos excluídos pelos arquivos `.gitignore` do Flutter.
