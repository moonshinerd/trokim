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

```bash
# Instalar dependências
flutter pub get

# Executar no emulador Android
flutter run
```
