# Validação do chat generativo — issue #25

Implementação baseada na `main` em `894c69a`, em 13/11/2026.
Referência: [issue #25](https://github.com/moonshinerd/trokim/issues/25).

## Verificações desta implementação

| Verificação | Resultado observado |
|---|---|
| Revisão do contrato FastAPI e da chamada Flutter | Cliente envia `message` e `mode: grounded` para `/v1/chat/generate`; modelos recebem o contrato completo |
| Revisão do timeout | Geração usa 90 segundos por padrão, configuráveis por `CHAT_GENERATE_TIMEOUT_SECONDS`; demais chamadas mantêm 15 segundos |
| `git diff --check` | Aprovado |
| `flutter analyze` e `flutter test` | Não executados: Flutter/Dart não encontrados no ambiente; acesso ao servidor de distribuição falhou por DNS |
| Testes da API (`test_generation.py`, `test_chat_api.py`, `test_request_lifecycle.py`) | 28 passaram após a revisão. Testes dos endpoints usam FakeEmbedder e SQLite temporário, sem depender do cache/modelo FastEmbed |
| Ruff nos arquivos Python alterados | `ruff check` e `ruff format --check` aprovados |
| CI mobile | Job adicionado com Flutter 3.50.0 fixado, dependências fixadas, formatação, análise e testes; ainda não executado nesta branch |
| Ollama | Executável 0.32.0 encontrado no aplicativo instalado; conexão a `127.0.0.1:11434` bloqueada pelo ambiente. Modelo disponível não confirmado |
| Emulador/dispositivo Android | Não executado: SDK/emulador não encontrados nos caminhos usuais |

Os testes Flutter foram atualizados para o contrato generativo e ampliados para
rejeição de payloads inconsistentes, falhas HTTP, timeout independente, resposta
longa, carregamento em tela estreita e nova tentativa após falha do modelo.
Esses cenários ainda precisam ser executados com o SDK disponível.
Os testes Python existentes não validam a implementação Dart.

## Ajustes após a revisão de qualidade

- `AssistantStatus` é tipado; `answered` e a abstenção são derivados desse estado.
- Os construtores de resposta e evidência são privados; os campos de evidência
  são validados na própria classe, e o controlador não reinterpreta o contrato.
- A geração usa `AbortableRequest`, com cancelamento por timeout e fechamento do
  cliente, inclusive durante leitura do corpo; `http` exige no mínimo 1.6.0.
- A API cancela a coroutine de geração ao detectar desconexão e aguarda sua
  limpeza. Um teste ASGI cobre desconexão durante operação pendente e nova
  tentativa, sem servidor externo.
- Foram acrescentados testes Flutter para abortar antes de repetir, ignorar a
  conclusão tardia, cancelar durante o corpo/fechamento e validar os modelos.
  Esses testes Dart ainda não foram executados neste ambiente.
- O CI passa a verificar o aplicativo; sua aprovação continua pendente.

O cancelamento da conexão não comprova parada imediata do processamento interno
do Ollama. A detecção da desconexão na API é cooperativa e ocorre entre pontos de
execução assíncrona; etapas síncronas de recuperação não são interrompidas no meio.

**A homologação ponta a ponta permanece pendente.** Este registro não comprova
desempenho, geração com modelo real, funcionamento dos links em Android ou
aprovação dos critérios de aceite da issue.

## Roteiro de homologação no Android

Siga a configuração do [README](README.md), com Ollama, modelo, embeddings e
corpus preparados previamente. Execute `flutter analyze`, `flutter test` e
`flutter build apk --debug` antes da demonstração.

Registre data, commit, versões do Flutter/Android/Ollama, modelo/tag, dispositivo,
URL local da API, `LLM_TIMEOUT` e `CHAT_GENERATE_TIMEOUT_SECONDS`. Identifique o
corpus e confirme a configuração local do provedor. Use apenas dados sintéticos.

| Cenário | Procedimento | Resultado esperado | Situação |
|---|---|---|---|
| Fundamentação | Perguntar como montar uma reserva de emergência | Resposta gerada, cartões e trechos; request em `/generate` com modo `grounded` | Pendente |
| Auditoria e fontes | Ativar Auditoria, expandir cartão e abrir fonte | Metadados preservados e documento oficial aberto no navegador | Pendente |
| Abstenção | Pedir um poema sobre futebol | Aviso pedagógico, sem cartões, com perguntas rápidas | Pendente |
| Backend indisponível | Parar a API e enviar pergunta | Erro amigável e ação de nova tentativa | Pendente |
| Modelo indisponível | Manter API ativa e parar Ollama ou configurar modelo inexistente | Erro amigável, sem abstenção nem fallback extrativo | Pendente |
| Timeout | Configurar prazo curto da geração e enviar pergunta que precise do modelo | Aviso de demora; interface volta a permitir interação | Pendente |
| Nova tentativa | Restaurar serviço/prazo e tentar novamente | Resposta sem duplicar o balão da pergunta | Pendente |
| Responsividade | Conferir resposta longa e cartões em tela estreita e ampla | Rolagem utilizável, sem cortes ou overflow, inclusive durante carregamento | Pendente |
| Privacidade | Conferir destinos de rede e configuração durante a demonstração | Pergunta processada pela API e modelo locais; navegação externa somente ao abrir fonte | Pendente |

Após cada cenário, acrescente resultado real e evidência correspondente. Se a
pergunta proposta não produzir o estado esperado, registre o desvio; não substitua
resultados observados por expectativas. Disponibilize o registro atualizado para
a consolidação da issue #26.

## Correção da instalação de dependências no CI

A execução 43441816963 da PR #46 falhou antes da análise/testes, com Flutter
3.50.0 e Dart 3.14.0. O workflow agora fixa Flutter 3.50.0. As entradas de
`listen`, `meta`, `test_api` e `vector_math` foram alinhadas ao lockfile oficial
desse SDK, incluindo os hashes publicados. `vector_math` permanece em 2.4.3,
compatível com o requisito `^2.4.3` do SDK, sem exigir a atualização para 2.4.4
sugerida pelo resolvedor na execução anterior.

Fonte: https://github.com/flutter/flutter/blob/3.50.0/pubspec.lock

O SDK segue indisponível neste ambiente, e o download falhou por DNS. Foram
conferidos os YAMLs, as entradas oficiais e o diff. A instalação com
`--enforce-lockfile`, a formatação, a análise e os testes ainda exigem nova
execução no CI; não foram declarados aprovados por esta correção.
