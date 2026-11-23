# 0025 — Armazenamento no aparelho e API sem estado

- **Status:** Aceita (completa a [ADR 0024](0024-persistencia-local-e-backup-criptografado.md))
- **Data:** 23/11/2026
- **Requisitos / GQs:** RF31, RF32, RNF01, RNF05; GQ03, GQ06
- **Issues:** [#104](https://github.com/moonshinerd/trokim/issues/104)

## Contexto

A ADR 0024 fez a biblioteca sobreviver ao reinício, mas o dado continuava no `trokim.db` da API,
sem criptografia em repouso. A ideia original do projeto é que os dados bancários e pessoais
fiquem **só no celular** do usuário, com backup exportável.

Os cálculos (resumo, parcelas, transferências) rodam em Python na API e precisam dos lançamentos
([ADR 0004](0004-calculos-deterministicos.md)). Reescrevê-los em Dart duplicaria a regra e quebraria
a fonte única de verdade.

## Decisão

1. **O aparelho é a fonte da verdade.** O app guarda o retrato da biblioteca (`LibrarySnapshot`,
   o mesmo contrato do backup) em um arquivo cifrado com **AES-256-GCM** na pasta privada do app.
   A chave de 256 bits é gerada no aparelho e fica no armazenamento seguro do sistema (Keystore
   no Android). Sem a chave, o arquivo é ilegível, e um byte alterado faz a leitura falhar.
2. **A API fica sem estado de longo prazo.** Ao abrir o app, ele devolve o retrato à API
   (`PUT /v1/library/snapshot`), que o mantém só em memória. Depois de cada alteração o app lê o
   retrato atualizado (`GET /v1/library/snapshot`) e regrava o arquivo. O `trokim.db` da API
   deixa de ser necessário para o app: `LIBRARY_PERSISTENCE=false` o desliga.
3. **O cálculo continua na API**, que só recebe o retrato quando o próprio usuário a hospeda
   (a máquina dele ou o Docker local). Por isso o requisito "nenhum lançamento cru sai do
   aparelho" vale **para servidores de terceiros**, não para a API do usuário. Hospedar a API
   fora exigiria enviar só agregados, o que fica como evolução e não é feito aqui.
4. **Migração.** Se o aparelho ainda não tem arquivo e a API já tem dados (versão antiga do app),
   o app traz os dados da API para o aparelho na primeira abertura. Se a API estiver fora do ar,
   nada é apagado: o arquivo do aparelho permanece e a sincronização repete na próxima abertura.
5. **Backup do Android desligado** (`allowBackup=false`): a cópia automática do Google levaria o
   arquivo sem a chave, que não sai do Keystore.
6. O backup `.trokim` ([ADR 0024](0024-persistencia-local-e-backup-criptografado.md)) segue como
   o caminho para trocar de aparelho; ao restaurar, o app grava o resultado no aparelho.

## Consequências

- Os dados do usuário passam a existir, cifrados, no aparelho; perder o aparelho sem backup é
  perder os dados (por isso o backup continua em destaque em Ajustes).
- A API em memória precisa do retrato a cada partida; o app cuida disso na abertura.
- Alterações feitas por outro caminho que não o app (por exemplo, `curl`) não chegam ao aparelho
  até a próxima alteração feita pelo app.
- Escolhemos AES-GCM em arquivo, e não SQLCipher: a biblioteca é um documento único que a API
  consome inteiro, e o SQLCipher exigiria um esquema de banco duplicado no Dart sem ganho de
  consulta.

## Alternativas descartadas

- **Reescrever os cálculos em Dart:** cumpre o critério original, mas duplica a regra e é grande
  demais para a semana.
- **Só cifrar o `trokim.db` no servidor:** não separa o dado do aparelho do dado do servidor.
