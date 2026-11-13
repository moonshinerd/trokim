# 0013 — Preferências salvas localmente e aba de Ajustes

- **Status:** Aceita
- **Data:** 13/11/2026
- **Requisitos / GQs:** RF15, RNF01, RNF10; GQ01, GQ03
- **Issue:** #39

## Contexto

O usuário não tinha como escolher o tema, reduzir animações ou verificar se o
app alcançava o backend local. Qualquer preferência persistida precisa respeitar
a premissa local-first: nada pode sair do aparelho.

## Decisão

Criar a aba **Ajustes** com tema (sistema, claro, escuro), reduzir animações,
abertura animada, teste de conexão (`GET /health`, timeout de 4 s) e texto de
privacidade. As preferências são salvas no aparelho com `shared_preferences` e
expostas por um `SettingsController` (`ChangeNotifier`) distribuído por um
`SettingsScope` (`InheritedNotifier`), sem acrescentar uma biblioteca de gestão de
estado.

## Consequências

Preferências persistem entre sessões sem qualquer transmissão externa. A opção
"reduzir animações" vale para todo o app. Passa a existir uma dependência nova
(`shared_preferences`). O endereço da API é exibido, mas ainda não editável.
