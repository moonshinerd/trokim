# 0001 — Adoção do Flutter para Desenvolvimento do App Android

- **Status:** Aceita
- **Data:** 04/11/2026
- **Requisitos / GQs:** RF07, RNF03, GQ07

## Contexto
O projeto Trokim necessita de uma interface mobile de alta qualidade para usuários do sistema operacional Android. A interface deve exibir resumos financeiros, gráficos intuitivos de despesas por categoria, permitir upload de arquivos de extrato (OFX e PDF) e disponibilizar um canal conversacional com o assistente inteligente. Além disso, como o desenvolvimento é apoiado ativamente por agentes de inteligência artificial (LLMs), a tecnologia escolhida deve possuir forte suporte sintático e previsibilidade arquitetural para geração de código.

## Decisão
Adotar o **Flutter (Dart)** para a aplicação móvel Android. O projeto será estruturado em arquitetura modular (*feature-first*), separando apresentação, controladores de estado e camada de cliente HTTP.

## Alternativas Consideradas
- **React Native (Expo / TypeScript):** Excelente flexibilidade e ampla base de treinamento para LLMs, mas o Flutter oferece uma árvore de componentes de interface mais consistente para o ecossistema Android e tipagem estrita com Dart.
- **Kotlin nativo (Jetpack Compose):** Stack oficial do Android, porém exige maior complexidade de configuração e dependências do Gradle, com menor agilidade na criação de protótipos de telas durante o curto ciclo de 7 semanas do CBL.

## Consequências
- **Positivas:**
  - Desempenho nativo com renderização fluida no Android.
  - Tipagem estática robusta com Dart, prevenindo falhas de runtime em telas financeiras.
  - Facilidade para agentes de IA gerarem e refatorarem widgets modulares e testáveis.
- **Negativas / Riscos:**
  - Exige a instalação do Flutter SDK e Android Toolchain no ambiente local para compilação de binários nativos.
