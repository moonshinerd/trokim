# 0022 — Registro de perfis de banco, níveis de suporte e tutoriais guiados

- **Status:** Aceita
- **Data:** 23/11/2026
- **Requisitos / GQs:** RF29, RF15; GQ01, GQ03
- **Issues:** [#92](https://github.com/moonshinerd/trokim/issues/92), [#93](https://github.com/moonshinerd/trokim/issues/93)
- **ADRs relacionadas:** [0005](0005-importacao-local-ofx-pdf.md), [0017](0017-perfis-de-banco-e-natureza-do-lancamento.md), [0018](0018-contas-periodos-transferencias-e-visoes.md)

## Contexto

O Trokim iniciou seu suporte a extratos com foco em Nubank (fatura e conta em OFX, pessoal e empresas) e Banco do Brasil (fatura Ourocard em PDF e conta corrente em OFX). Na Semana 5, o suporte é ampliado para mais cinco instituições financeiras populares no Brasil: **PicPay**, **Mercado Pago**, **Banco Inter**, **C6 Bank** e **Itaú**.

Cada banco possui particularidades operacionais: caminhos distintos nos menus dos aplicativos móveis, diferentes formatos gerados (OFX, PDF de extrato, PDF de fatura) e diferentes níveis de certeza na extração dos lançamentos. Usuários precisam saber exatamente como exportar seus arquivos sem frustração e, fundamentalmente, qual o nível de maturidade e confiabilidade daquele banco no Trokim.

## Decisão

1. **Dois níveis explícitos de suporte (Validado vs. Experimental):**
   - **Validado:** Bancos que foram exaustivamente testados e conciliados ponta a ponta com arquivos e extratos de contas reais. Integram esta categoria: **Nubank**, **Banco do Brasil**, **PicPay** e **Mercado Pago**.
   - **Experimental:** Bancos cujos tutoriais e perfis foram elaborados a partir das centrais de ajuda oficiais e documentação pública das instituições, mas que ainda não foram homologados com arquivos de contas reais pela equipe. Integram esta categoria: **Banco Inter**, **C6 Bank** e **Itaú**.
2. **Transparência e vedação a promessas inverídicas:**
   Nenhum tutorial ou tela pode afirmar que um banco experimental possui suporte validado. A interface móvel e a documentação devem estampar selos visuais explícitos (`Validado` com realce positivo e `Experimental` com realce âmbar/ouro) e avisos contextuais antes e durante a exibição dos passos.
3. **Catálogo unificado no app (`supportedBanks`):**
   O domínio do cliente móvel centraliza os metadados de cada banco em `mobile/lib/features/import_guide/domain/import_guides.dart` (`SupportedBankInfo`), definindo identificador, nome, nível de suporte, formatos aceitos, descrição e tutoriais.
4. **Tutoriais passo a passo com foco em ação:**
   Cada banco possui tutorial próprio de 3 a 5 passos curtos (`GuideStep`), com ícones representativos, indicando onde encontrar o botão de exportar no app da instituição e qual formato escolher.
5. **Autonomia do usuário e atalhos:**
   O tutorial nunca é obrigatório:
   - Em todas as etapas há o botão **Pular tutorial**.
   - Na tela inicial de bancos suportados, o botão **Já tenho o arquivo** permite avançar imediatamente ao seletor.
   - O checkbox **Não mostrar este tutorial de novo** no último passo (reativável a qualquer momento em Ajustes) salva a preferência no próprio aparelho.
6. **Fallback genérico e abertura à comunidade:**
   Arquivos de bancos não catalogados podem ser importados via opção **Outro banco** (processados pelo parser genérico). Quando o banco não for reconhecido, o app exibe uma seção de ajuda orientando o envio e disponibiliza o atalho **Pedir suporte a um banco**, direcionando o usuário para abertura de issue no repositório GitHub.

## Consequências

- O usuário obtém instruções diretas e precisas de como obter seus arquivos em cada aplicativo bancário.
- Redução drástica de falhas de importação decorrentes do envio de formatos não suportados (ex.: envio de PDF quando o banco só disponibiliza OFX, ou vice-versa).
- Clareza sobre a maturidade do suporte, prevenindo falsas expectativas sobre bancos em estágio experimental.
- Facilidade para estender novos bancos: basta cadastrar a instituição no enum, no catálogo e implementar os passos curtos do tutorial.

## Alternativas descartadas

- **Tratar todos os bancos igualmente sem selo:** Rejeitado porque bancos não testados em contas reais podem apresentar variações não mapeadas no layout, e a transparência é pilar inegociável do projeto.
- **Tutorial obrigatório a cada importação:** Rejeitado por comprometer a usabilidade e a agilidade de usuários recorrentes.
- **Depender apenas de Open Finance:** Rejeitado (conforme [ADR 0005](0005-importacao-local-ofx-pdf.md)) em prol da soberania local-first e privacidade dos dados.

