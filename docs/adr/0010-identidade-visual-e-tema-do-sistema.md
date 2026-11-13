# 0010 — Identidade visual, design system e tema claro/escuro pelo sistema

- **Status:** Aceita
- **Data:** 13/11/2026
- **Requisitos / GQs:** RNF03, RNF10; GQ01, GQ07
- **Issues:** #38, #41, #42

## Contexto

A interface usava a paleta azul padrão do Material e só tinha tema claro. O time
pediu uma identidade própria e que o app respeitasse a configuração do aparelho,
com o modo escuro como referência visual. Cores fixas espalhadas pelas telas
impediam trocar de tema sem reescrever cada uma.

## Decisão

- **Paleta oficial:** Champagne `#FAEBD7`, Tidewater Green `#2F4F4F` e Fortuna
  Gold `#DAA520`. No escuro o verde assume o fundo e o bege escurece, virando
  texto suave.
- **Tema pelo sistema:** `ThemeMode.system` por padrão, com opção de fixar claro
  ou escuro em Ajustes (ADR 0012).
- **Tokens centralizados:** `AppTheme` (marca e semânticas) e a `ThemeExtension`
  `AppColors` (fundo, superfície, contorno, texto, realce), lida por
  `context.colors`. Telas não usam cores de superfície fixas.
- **Tipografia embarcada:** Plus Jakarta Sans (OFL), sem depender de rede.
- **Movimento:** transições por *fade* e deslize, entradas escalonadas e
  números animados, todos desativados por "reduzir movimento" do sistema ou de
  Ajustes. Rolagem sem o efeito de esticar do Android 12+.
- **MkDocs:** mesma paleta, claro e escuro por `prefers-color-scheme`, e
  navegação instantânea com transição suave.
- **Toolchain Android:** AGP 9.3.1, Gradle 9.5.0 e Kotlin 2.4.20, exigidos pelo
  Flutter estável (3.50).

## Consequências

Trocar de tema ou ajustar a paleta é uma mudança em um único arquivo. Há custo de
manter dois temas coerentes. O site e o app compartilham identidade. A tela
Resumo ainda exibe valores de exemplo, sinalizados na interface.
