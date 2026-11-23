import 'dart:async';

import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:intl/intl.dart';
import 'package:trokim/core/network/api_client.dart';
import 'package:trokim/core/settings/settings_controller.dart';
import 'package:trokim/features/dashboard/presentation/dashboard_screen.dart';
import 'package:trokim/features/finance/data/finance_repository.dart';
import 'package:trokim/features/finance/presentation/finance_controller.dart';

import 'support/finance_fixtures.dart';

final _brl = NumberFormat.currency(locale: 'pt_BR', symbol: 'R\$');

Future<void> _open(WidgetTester tester, FinanceController finance) async {
  final settings = SettingsController.memory()..setReduceMotion(true);
  addTearDown(settings.dispose);
  addTearDown(finance.dispose);
  await tester.pumpWidget(
    SettingsScope(
      controller: settings,
      child: FinanceScope(
        controller: finance,
        child: const MaterialApp(home: DashboardScreen()),
      ),
    ),
  );
}

void main() {
  testWidgets('mostra o resumo calculado pela API, sem rótulo de exemplo', (
    tester,
  ) async {
    final api = FakeFinanceApi();
    final finance = api.controller();
    await _open(tester, finance);
    await tester.runAsync(finance.load);
    await tester.pump(const Duration(seconds: 2));

    expect(find.text(_brl.format(2849.5)), findsOneWidget);
    expect(find.text(_brl.format(5000)), findsOneWidget);
    expect(find.text(_brl.format(2150.5)), findsOneWidget);
    expect(find.text('Moradia'), findsOneWidget);
    expect(find.text(_brl.format(1500)), findsOneWidget);
    expect(find.text('Alimentação'), findsOneWidget);
    expect(find.text('Outros'), findsOneWidget);
    expect(find.text('dados de exemplo'), findsNothing);
    // Categorias em ordem decrescente de gasto.
    final moradia = tester.getTopLeft(find.text('Moradia')).dy;
    final alimentacao = tester.getTopLeft(find.text('Alimentação')).dy;
    expect(moradia, lessThan(alimentacao));
  });

  testWidgets('enquanto carrega mostra o indicador de progresso', (
    tester,
  ) async {
    final pending = Completer<http.Response>();
    final finance = FinanceController(
      FinanceRepository(
        () => ApiClient(client: MockClient((_) => pending.future)),
      ),
    );
    await _open(tester, finance);
    unawaited(finance.load());
    await tester.pump();

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    pending.complete(jsonResponse(summaryJson));
    await tester.pump();
  });

  testWidgets('sem extratos importados orienta a importar', (tester) async {
    final api = FakeFinanceApi(summary: emptySummaryJson, transactions: []);
    final finance = api.controller();
    await _open(tester, finance);
    await tester.runAsync(finance.load);
    await tester.pump();

    expect(find.text('Nenhum extrato importado ainda'), findsOneWidget);
    expect(find.text(_brl.format(0)), findsNothing);
  });

  testWidgets('API fora do ar mostra erro e "Tentar novamente" recarrega', (
    tester,
  ) async {
    final api = FakeFinanceApi()..offline = true;
    final finance = api.controller();
    await _open(tester, finance);
    await tester.runAsync(finance.load);
    await tester.pump();

    expect(find.text('Sem conexão com a API local'), findsOneWidget);

    api.offline = false;
    await tester.runAsync(() async {
      await tester.tap(find.text('Tentar novamente'));
      await finance.load();
    });
    await tester.pump(const Duration(seconds: 2));

    expect(find.text('Sem conexão com a API local'), findsNothing);
    expect(find.text(_brl.format(2849.5)), findsOneWidget);
  });
}
