import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:trokim/core/settings/settings_controller.dart';
import 'package:trokim/features/finance/presentation/finance_controller.dart';
import 'package:trokim/features/transactions/presentation/transactions_screen.dart';

import 'support/finance_fixtures.dart';

Future<void> _open(
  WidgetTester tester,
  FinanceController finance, {
  StatementPicker? picker,
  bool tutorial = false,
}) async {
  final settings = SettingsController.memory()
    ..setReduceMotion(true)
    ..setShowImportTutorial(tutorial);
  addTearDown(settings.dispose);
  addTearDown(finance.dispose);
  await tester.pumpWidget(
    SettingsScope(
      controller: settings,
      child: FinanceScope(
        controller: finance,
        child: MaterialApp(home: TransactionsScreen(pickFile: picker)),
      ),
    ),
  );
}

void main() {
  testWidgets('lista os arquivos realmente importados, com duplicatas', (
    tester,
  ) async {
    final finance = FakeFinanceApi().controller();
    await _open(tester, finance);
    await tester.runAsync(finance.load);
    await tester.pump();

    expect(find.text('extrato_novembro.ofx'), findsOneWidget);
    expect(
      find.text('2 transações importadas • sem duplicatas'),
      findsOneWidget,
    );
    expect(find.text('fatura_cartao.pdf'), findsOneWidget);
    expect(
      find.text('1 transação importada • 1 duplicata evitada'),
      findsOneWidget,
    );
    expect(find.text('dados de exemplo'), findsNothing);
  });

  testWidgets('sem arquivos mostra o estado vazio', (tester) async {
    final finance = FakeFinanceApi(transactions: []).controller();
    await _open(tester, finance);
    await tester.runAsync(finance.load);
    await tester.pump();

    expect(find.text('Nenhum arquivo importado ainda.'), findsOneWidget);
  });

  testWidgets('importar envia o arquivo escolhido e atualiza a lista', (
    tester,
  ) async {
    final api = FakeFinanceApi(transactions: []);
    final finance = api.controller();
    await _open(
      tester,
      finance,
      picker: () async => PickedStatement('novo.ofx', () async => [1, 2, 3]),
    );
    await tester.runAsync(finance.load);
    await tester.pump();

    // Depois do envio, a API passa a listar o arquivo.
    api.onUpload = (_) {
      api.transactions = [
        {'source_file': 'novo.ofx', 'is_duplicate': false},
        {'source_file': 'novo.ofx', 'is_duplicate': false},
      ];
      return jsonResponse({
        'filename': 'novo.ofx',
        'imported_count': 2,
        'duplicate_count': 0,
      });
    };

    await tester.runAsync(() async {
      await tester.tap(find.text('Importar extrato'));
      await Future<void>.delayed(const Duration(milliseconds: 100));
    });
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(api.count('POST', '/transactions/upload'), 1);
    await tester.pumpAndSettle();
    expect(find.text('Pronto!'), findsOneWidget);
    expect(find.text('2 lançamentos lidos'), findsOneWidget);
    await tester.tap(find.text('Concluir'));
    await tester.pumpAndSettle();
    expect(find.text('novo.ofx'), findsOneWidget);
  });

  testWidgets('erro da API aparece na mensagem e nada é listado', (
    tester,
  ) async {
    final api = FakeFinanceApi(transactions: [])
      ..onUpload = (_) => jsonResponse({
        'detail': 'Erro ao processar arquivo OFX: arquivo vazio',
      }, 400);
    final finance = api.controller();
    await _open(
      tester,
      finance,
      picker: () async => PickedStatement('vazio.ofx', () async => [0]),
    );
    await tester.runAsync(finance.load);
    await tester.pump();

    await tester.runAsync(() async {
      await tester.tap(find.text('Importar extrato'));
      await Future<void>.delayed(const Duration(milliseconds: 100));
    });
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    await tester.pumpAndSettle();
    expect(find.text('Não deu para importar'), findsOneWidget);
    expect(
      find.text('Erro ao processar arquivo OFX: arquivo vazio'),
      findsOneWidget,
    );
    expect(find.text('Escolher outro arquivo'), findsOneWidget);
  });

  testWidgets('cancelar o seletor não chama a API', (tester) async {
    final api = FakeFinanceApi();
    final finance = api.controller();
    await _open(tester, finance, picker: () async => null);
    await tester.runAsync(finance.load);
    await tester.pump();

    await tester.runAsync(() async {
      await tester.tap(find.text('Importar extrato'));
      await Future<void>.delayed(const Duration(milliseconds: 50));
    });
    await tester.pump();

    expect(api.count('POST', '/transactions/upload'), 0);
  });
}
