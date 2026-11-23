# Protótipo do aplicativo

Esta demonstração estática apresenta cinco telas do Trokim em uma navegação semelhante à do aplicativo. Use a barra inferior para alternar entre **Resumo**, **Extratos**, **Assistente**, **Cenários** e **Ajustes**. Com o foco dentro da demonstração, `Alt+1` a `Alt+5` também troca de tela, inclusive em teclados nos quais `Alt` modifica o caractere digitado.

<iframe src="../prototipo/demo.html" title="Protótipo navegável do aplicativo Trokim" width="100%" height="900" loading="lazy" style="border: 1px solid #e6d2b3; border-radius: 16px;"></iframe>

[Abrir o protótipo em uma página própria](prototipo/demo.html).

## O que corresponde ao aplicativo

- Paleta Champagne, Tidewater Green e Fortuna Gold, tipografia Plus Jakarta Sans embarcada e cartões arredondados seguem a [ADR 0011](adr/0011-identidade-visual-e-tema-do-sistema.md).
- A navegação inferior e os nomes das cinco áreas refletem as telas do app.
- O tema acompanha `prefers-color-scheme`, a preferência do sistema operacional. As transições respeitam `prefers-reduced-motion`.
- A conversa mostra uma resposta acompanhada de uma fonte institucional clicável, como no cartão de evidência do app.

## O que é simulado

Todos os lançamentos, saldos, categorias, mensagens, fontes associadas à conversa e valores de cenários são exemplos sintéticos criados para esta demonstração. O protótipo não importa arquivos, consulta API, executa cálculos, envia mensagens nem salva preferências. Os controles sem navegação são apenas visuais. O link da fonte só abre o site do Banco Central se selecionado e houver conexão; a demonstração e seus arquivos carregam sem serviços externos.

O layout se adapta a telas estreitas e largas; em desktop, a interface fica centralizada. Os arquivos são HTML, CSS e JavaScript estáticos, sem bibliotecas externas, CDN ou fontes remotas. O contorno de foco visível permite navegar pelos controles usando teclado.

O iframe usa um caminho relativo compatível com a página publicada em `/prototipo/`, inclusive quando o site está em um subdiretório. Os endereços `#resumo`, `#extratos`, `#assistente`, `#cenarios` e `#ajustes` abrem a tela correspondente; um fragmento desconhecido retorna ao Resumo.

## Captura e revisão de documentos no app

O aplicativo também oferece **Fotografar ou escolher documento** em **Extratos**
e no primeiro passo de **Importar extrato**. Esse fluxo ainda não é interativo
no protótipo estático: a [seção de documentos do Guia de Uso](guia-de-uso.md#810-fotografar-ou-escolher-documento)
mostra a captura sintética da tela e descreve prévia, confiança, correções,
bloqueios e descarte. No app, a leitura desta fase é simulada, sem criar
lançamentos; a integração real pertence à issue #97.
