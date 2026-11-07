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
│   │   └── theme/            # Design System (Material 3)
│   └── features/
│       ├── dashboard/        # Resumo de receitas, despesas e poupança
│       ├── transactions/     # Importação e listagem de extratos OFX/PDF
│       ├── chat_assistant/   # Chat consultivo com RAG oficial
│       └── budget_scenarios/ # Simulador e comparador de cenários
```

---

## Execução

Requer Flutter stable e, para gerar o APK, JDK 17 e Android SDK 36 (ver
[Validação local](#validacao-local)). Se o Flutter não estiver no `PATH`, use o
caminho completo do executável nos comandos abaixo.

### Backend local

Na raiz do repositório, em um terminal separado:

```bash
make setup
make api-run
```

A API deve oferecer `POST /v1/chat/ask`, recebendo `message` e retornando `answered`,
`status`, `answer` e `evidences`. O chat não calcula valores financeiros nem usa
chaves de provedor no aplicativo. As evidências preservam instituição, título,
seção e URL; `document_id` e `source_url` podem estar ausentes ou nulos.

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
caracteres. Respostas fundamentadas exibem cards com fontes e URLs selecionáveis;
abstenções aparecem com aviso e sem cards. Falha de conexão, timeout de 15 segundos
ou erro HTTP geram mensagem amigável e a ação **Tentar novamente**, que repete a
última pergunta com erro sem duplicar seu balão.

## Validação local

Na pasta `mobile/`:

```bash
flutter analyze
flutter test
flutter build apk --debug
```

Os testes usam `MockClient`, sem backend ativo nem rede. Cobrem conversão de
respostas, metadados opcionais, erros HTTP/conexão/timeout, concorrência e ciclo
de vida do controlador, cards, abstenção, carregamento e nova tentativa na tela.
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
