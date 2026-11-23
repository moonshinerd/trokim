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

### Fluxo de importação e tela de bancos suportados

O protótipo estático web foca na navegação das cinco abas principais e na identidade visual, não executando o upload ou processamento de arquivos (o botão de importar extrato na aba Extratos é apenas demonstrativo). O fluxo interativo completo de importação — incluindo a **tela de Bancos Suportados** com selos de validação (**Validado** e **Experimental**), formatos aceitos e tutoriais passo a passo navegáveis para cada banco ([RF29](requisitos.md), [ADR 0022](adr/0022-registro-de-perfis-e-niveis-de-suporte.md)) — é implementado e testado de forma nativa no aplicativo Flutter para Android (`mobile/lib/features/import_guide/`), funcionando em modo local-first no dispositivo. Veja os tutoriais detalhados de cada instituição no [Guia de Uso](guia-de-uso.md#82-importar-por-banco-e-bancos-suportados-rf29).

O iframe usa um caminho relativo compatível com a página publicada em `/prototipo/`, inclusive quando o site está em um subdiretório. Os endereços `#resumo`, `#extratos`, `#assistente`, `#cenarios` e `#ajustes` abrem a tela correspondente; um fragmento desconhecido retorna ao Resumo.
