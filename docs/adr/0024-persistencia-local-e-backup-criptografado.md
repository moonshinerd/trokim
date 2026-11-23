# 0024 — Persistência local da biblioteca e backup criptografado

- **Status:** Aceita
- **Data:** 23/11/2026
- **Requisitos / GQs:** RF31, RF32, RNF01, RNF05; GQ03, GQ06
- **Issues:** [#102](https://github.com/moonshinerd/trokim/issues/102)
- **ADRs relacionadas:** [0002](0002-fastapi-sqlite-local.md), [0015](0015-dados-reais-importacao-e-endereco-da-api.md), [0019](0019-orm-e-migracoes-numeradas.md)

## Contexto

A biblioteca do usuário (lançamentos, contas, arquivos, transferências confirmadas e regras de
categoria) vivia só na memória da API ([ADR 0015](0015-dados-reais-importacao-e-endereco-da-api.md)):
reiniciar apagava tudo. Isso já era uma pendência assumida desde a Semana 3 e passou a bloquear
o chat com as contas do usuário e a importação por foto da Semana 5, que dependem de dados que
sobrevivam a um reinício.

A premissa do projeto é que **dado bancário e pessoal fica sob controle do usuário**. Isso pede
uma separação explícita do que é guardado no aparelho e do que pode ir a um servidor, e um modo de
levar os dados para outro aparelho sem passar por terceiros.

## Decisão

1. **Separação dos dados.**

   | Dado | Onde fica | Pode ir ao servidor? |
   |---|---|---|
   | Lançamentos, contas, arquivos, transferências, regras de categoria, histórico do chat | Com o usuário (SQLite local) | Não, nunca em bruto |
   | Totais, categorias e parcelas **agregados** de uma pergunta | Só durante a requisição | Sim, sem lançamento cru, CPF, conta nem agência |
   | Corpus oficial (RAG), modelos, OCR, regras de cálculo | Servidor | Sim, não são dado pessoal |
   | Imagem de documento | Memória, só durante a leitura | Não é gravada |

2. **Persistência atrás de uma porta.** `LibraryRepository` (`app/models/library_repository.py`)
   tem `load` e `save`. O adaptador `SqliteLibraryRepository` grava na tabela `library_snapshot`
   (migração numerada `002`, [ADR 0019](0019-orm-e-migracoes-numeradas.md)). A biblioteca é
   restaurada ao iniciar a API e gravada depois de cada rota que a altera (middleware ASGI puro),
   apenas quando o conteúdo mudou. `LIBRARY_PERSISTENCE=false` desliga a gravação.
3. **Retrato versionado.** O estado inteiro vira um `LibrarySnapshot` (`app/domain/snapshot.py`,
   `version = 1`) em JSON, o mesmo formato do banco e do backup. É uma linha por banco, gravada de
   uma vez (atômica). As tabelas normalizadas ficam para quando o volume pedir consulta por SQL.
4. **Backup criptografado `.trokim`.** `POST /v1/backup/export` devolve o arquivo e
   `POST /v1/backup/import` o restaura (`substituir` ou `mesclar`, sem duplicar lançamentos).
   Formato: gzip e **AES-256-GCM**, com chave derivada da **senha do usuário por scrypt**
   (sal e nonce aleatórios, cabeçalho autenticado). A senha tem pelo menos 8 caracteres e **nunca é
   gravada nem registrada**. Senha errada, arquivo adulterado e versão mais nova são recusados com
   mensagem clara; o tamanho do arquivo e do conteúdo descomprimido é limitado.
5. **Campos privados.** O documento mascarado e a conta de destino do Pix, que a API nunca expõe,
   entram no retrato porque servem para reconhecer as contas próprias do usuário. Por isso o
   backup é sempre cifrado, e o banco local é do usuário.

## Consequências

- Reiniciar a API mantém lançamentos, contas e decisões. O chat e a importação por foto passam a
  trabalhar sobre dados duráveis.
- O arquivo `trokim.db` **não é criptografado em repouso**: quem tem o computador tem o banco. A
  criptografia em repouso entra com o armazenamento no aparelho (abaixo) e, no desktop, depende do
  disco cifrado do sistema. O backup, esse sim, é sempre cifrado.
- Esquecer a senha do backup é irrecuperável por desenho.
- Gravar o retrato inteiro a cada alteração é simples e atômico, mas cresce com o volume; a
  porta permite trocar por tabelas normalizadas sem mexer nas regras.

## Próximos passos (Semana 6)

- **Armazenamento no aparelho:** o app guarda a biblioteca em SQLite criptografado (SQLCipher) e a
  API passa a **não ter estado**, recebendo por requisição só o retrato agregado necessário. Esta
  ADR já fixa o contrato (`LibrarySnapshot`) e o que pode sair do aparelho.
- **Telas de backup no app** (Ajustes: exportar e importar, com o seletor de arquivos e
  "Compartilhar"). A API já está pronta.

## Alternativas descartadas

- **Reescrever os cálculos em Dart no aparelho:** duplica a regra e quebra a fonte única de
  cálculo da [ADR 0004](0004-calculos-deterministicos.md).
- **Servidor com conta e banco do usuário:** contraria a premissa de privacidade e traria
  obrigações de LGPD que o projeto não quer assumir.
- **Backup sem senha ou com chave do servidor:** quem tivesse o arquivo (ou o servidor) leria
  os extratos.
