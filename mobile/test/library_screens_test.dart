import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:trokim/core/format.dart';
import 'package:trokim/core/settings/settings_controller.dart';
import 'package:trokim/features/dashboard/presentation/dashboard_screen.dart';
import 'package:trokim/features/finance/domain/library_models.dart';
import 'package:trokim/features/finance/presentation/finance_controller.dart';
import 'package:trokim/features/installments/presentation/installments_screen.dart';
import 'package:trokim/features/transactions/presentation/transactions_screen.dart';
import 'package:trokim/features/transfers/presentation/transfers_screen.dart';

import 'support/finance_fixtures.dart';
import 'support/flow_harness.dart' show bodyOf;
import 'support/library_fixtures.dart';

/// API falsa com o cenário completo: contas, arquivos, parcelamentos e transferências.
FakeFinanceApi _api() {
  final api = FakeFinanceApi(transactions: libraryTransactionsJson)
    ..accounts = accountsJson
    ..statements = statementsJson
    ..installments = installmentsJson
    ..suggestions = suggestionsJson
    ..transfers = transfersJson;
  api.onSummary = (request) => summaryWithAccounts(
    owner: request.url.queryParameters['owner'] ?? 'todas',
    view: request.url.queryParameters['view'] ?? 'competencia',
  );
  return api;
}

Future<FinanceController> _open(
  WidgetTester tester,
  FakeFinanceApi api,
  Widget home,
) async {
  final finance = api.controller();
  final settings = SettingsController.memory()..setReduceMotion(true);
  addTearDown(settings.dispose);
  addTearDown(finance.dispose);
  await tester.pumpWidget(
    SettingsScope(
      controller: settings,
      child: FinanceScope(
        controller: finance,
        child: MaterialApp(home: home),
      ),
    ),
  );
  await tester.runAsync(finance.load);
  await tester.pumpAndSettle();
  return finance;
}

Future<void> _tapAsync(WidgetTester tester, Finder finder) async {
  await tester.runAsync(() async {
    await tester.tap(finder);
    await Future<void>.delayed(const Duration(milliseconds: 150));
  });
  await tester.pumpAndSettle();
}

Future<void> _scrollTo(WidgetTester tester, Finder finder) async {
  await tester.scrollUntilVisible(
    finder,
    200,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pumpAndSettle();
}

void main() {
  group('modelos da biblioteca', () {
    test('conta, arquivo, parcelamento e transferências da API', () {
      final accounts = accountsJson.map(
        (j) => AccountInfo.fromJson(Map<String, dynamic>.from(j)),
      );
      expect(accounts.first.isCard, isTrue);
      expect(accounts.last.owner, isNull);
      expect(accounts.last.needsOwner, isTrue);

      final data = StatementsData.fromJson(
        jsonDecode(jsonEncode(statementsJson)) as Map<String, dynamic>,
      );
      expect(data.statements.first.status, StatementStatus.open);
      expect(data.statements.first.status.isIncomplete, isTrue);
      expect(data.statements.last.status.isIncomplete, isFalse);
      expect(data.coverage['nubank:1111111-1']!.gaps, hasLength(1));

      final installments = InstallmentsData.fromJson(
        jsonDecode(jsonEncode(installmentsJson)) as Map<String, dynamic>,
      );
      expect(installments.isEmpty, isFalse);
      expect(installments.plans.last.finished, isTrue);
      expect(installments.projection.first.month, '2026-12');

      final suggestion = TransferSuggestion.fromJson(
        Map<String, dynamic>.from(suggestionsJson.first),
      );
      expect(suggestion.isCardPayment, isTrue);
      expect(suggestion.isHigh, isTrue);

      final handled = transfersJson
          .map((j) => OwnTransfer.fromJson(Map<String, dynamic>.from(j)))
          .toList();
      expect(handled.first.automatic, isTrue);
      expect(handled.last.automatic, isFalse);
      expect(handled.last.date, DateTime(2026, 10, 10));
    });

    test('situação desconhecida e resposta inválida', () {
      expect(StatementStatus.fromApi('x'), StatementStatus.unknown);
      expect(
        () => StatementsData.fromJson({'statements': 'x', 'coverage': {}}),
        throwsFormatException,
      );
      expect(
        () => InstallmentsData.fromJson({'plans': [], 'active_count': 0}),
        throwsFormatException,
      );
      expect(
        () => OwnTransfer.fromJson({'id': 'x', 'kind': 'automatica'}),
        throwsFormatException,
      );
    });
  });

  group('transferências entre contas', () {
    testWidgets('mostra a sugestão e as já tratadas', (tester) async {
      await _open(tester, _api(), const TransfersScreen());
      expect(find.text('Pagamento de fatura de outro banco'), findsOneWidget);
      expect(find.text(brl.format(750)), findsOneWidget);
      expect(find.text('Confiança alta'), findsOneWidget);
      expect(
        find.text('Nubank · conta  →  Banco do Brasil · cartão final 1234'),
        findsOneWidget,
      );
      expect(
        find.text('Transferência · ${brl.format(308.76)}'),
        findsOneWidget,
      );
      expect(
        find.textContaining('Reconhecida pela conta de destino'),
        findsOneWidget,
      );
      await _scrollTo(tester, find.textContaining('Confirmada por você'));
    });

    testWidgets('confirmar envia o par e avisa', (tester) async {
      final api = _api();
      await _open(tester, api, const TransfersScreen());
      await _tapAsync(tester, find.text('Confirmar'));
      final post = api.requests.singleWhere(
        (r) => r.url.path.endsWith('/transfers/confirm'),
      );
      expect(jsonDecode(bodyOf(post)), {'debit_uid': 'd1', 'credit_uid': 'c1'});
      expect(find.text('Pagamento de fatura confirmado.'), findsOneWidget);
    });

    testWidgets('"Não são" recusa a sugestão', (tester) async {
      final api = _api();
      await _open(tester, api, const TransfersScreen());
      await _tapAsync(tester, find.text('Não são'));
      expect(api.count('POST', '/transfers/reject'), 1);
      expect(find.text('Ok, não vou sugerir de novo.'), findsOneWidget);
    });

    testWidgets('desfazer uma automática desmarca pelo lançamento', (
      tester,
    ) async {
      final api = _api();
      await _open(tester, api, const TransfersScreen());
      await _tapAsync(tester, find.text('Desfazer').first);
      final unmark = api.requests.singleWhere(
        (r) => r.url.path.endsWith('/transfers/unmark'),
      );
      expect(jsonDecode(bodyOf(unmark)), {'uid': 'auto-1'});
      expect(
        find.text('Desfeito. O valor volta a contar nos totais.'),
        findsOneWidget,
      );
    });

    testWidgets('desfazer uma confirmada desfaz o par', (tester) async {
      final api = _api();
      await _open(tester, api, const TransfersScreen());
      await _scrollTo(tester, find.textContaining('Confirmada por você'));
      await _tapAsync(tester, find.text('Desfazer').last);
      final undo = api.requests.singleWhere(
        (r) => r.url.path.endsWith('/transfers/undo'),
      );
      expect(jsonDecode(bodyOf(undo)), {'id': 'par-1'});
    });

    testWidgets('falha na API mostra aviso', (tester) async {
      final api = _api()..onAction = (_) => jsonResponse({'detail': 'x'}, 500);
      await _open(tester, api, const TransfersScreen());
      await _tapAsync(tester, find.text('Confirmar'));
      expect(
        find.text('Não foi possível concluir. Tente novamente.'),
        findsOneWidget,
      );
    });

    testWidgets('sem nada para mostrar', (tester) async {
      await _open(tester, FakeFinanceApi(), const TransfersScreen());
      expect(find.text('Nada para confirmar agora.'), findsOneWidget);
      expect(
        find.text('Nenhuma transferência entre suas contas ainda.'),
        findsOneWidget,
      );
    });
  });

  group('parcelamentos', () {
    testWidgets('total, projeção, em andamento e quitados', (tester) async {
      await _open(tester, _api(), const InstallmentsScreen());
      expect(find.text(brl.format(1086.44)), findsOneWidget);
      expect(find.text('1 compra parcelada em andamento'), findsOneWidget);
      expect(find.text('dez/2026'), findsOneWidget);
      expect(find.text('jan/2027'), findsOneWidget);
      expect(find.text('Parcela 4 de 8'), findsOneWidget);
      expect(
        find.text('Faltam 4 · ${brl.format(1086.44)} · termina em mar/2027'),
        findsOneWidget,
      );
      await _scrollTo(tester, find.text('Quitado'));
      expect(find.text('Curso Exemplo'), findsOneWidget);
    });

    testWidgets('sem parcelamentos', (tester) async {
      await _open(tester, FakeFinanceApi(), const InstallmentsScreen());
      expect(
        find.text('Nenhum parcelamento encontrado nas faturas importadas.'),
        findsOneWidget,
      );
    });
  });

  group('filtros do Resumo', () {
    testWidgets('dono e visão pedem o resumo certo à API', (tester) async {
      final api = _api();
      await _open(tester, api, const DashboardScreen());
      expect(find.text('Tudo'), findsOneWidget);
      expect(find.text(brl.format(903.88)), findsOneWidget);
      await _tapAsync(tester, find.text('Empresas'));
      expect(find.text('-${brl.format(106.14)}'), findsOneWidget);
      await _tapAsync(tester, find.text('Caixa'));
      final last = api.requests.lastWhere(
        (r) => r.url.path.endsWith('/transactions/summary'),
      );
      expect(last.url.queryParameters, {'owner': 'empresa', 'view': 'caixa'});
      expect(find.textContaining('Caixa: só o que entrou'), findsOneWidget);
    });

    testWidgets('com um dono só, o filtro não aparece', (tester) async {
      final api = _api()..accounts = [accountsJson.first];
      await _open(tester, api, const DashboardScreen());
      expect(find.text('Tudo'), findsNothing);
      expect(find.text('Gastos'), findsOneWidget);
    });

    testWidgets('aviso de fatura aberta segue o filtro de dono', (
      tester,
    ) async {
      await _open(tester, _api(), const DashboardScreen());
      expect(find.text('Valores parciais'), findsOneWidget);
      await _tapAsync(tester, find.text('Empresas'));
      // a fatura aberta é da conta pessoal; no filtro Empresas só fica a lacuna da PJ
      expect(find.textContaining('Fatura aberta'), findsNothing);
      expect(
        find.textContaining('Nubank Empresas · conta: faltam arquivos'),
        findsOneWidget,
      );
      await _tapAsync(tester, find.text('Pessoal'));
      expect(find.textContaining('Fatura aberta'), findsOneWidget);
      expect(find.textContaining('faltam arquivos'), findsNothing);
    });

    testWidgets('por conta e card de parcelamentos', (tester) async {
      await _open(tester, _api(), const DashboardScreen());
      await _scrollTo(tester, find.text('Por conta'));
      expect(find.text('Nubank Empresas · conta'), findsOneWidget);
      expect(find.text('− ${brl.format(150)}'), findsOneWidget);
      await _scrollTo(tester, find.text('Parcelamentos'));
      expect(
        find.text('${brl.format(1086.44)} ainda a pagar · 1 compra'),
        findsOneWidget,
      );
    });
  });

  group('Extratos', () {
    testWidgets('situação dos arquivos, lacunas, atalhos e contas', (
      tester,
    ) async {
      await _open(tester, _api(), const TransactionsScreen());
      expect(find.text('Valores parciais'), findsOneWidget);
      expect(
        find.textContaining(
          'Nubank Empresas · conta: faltam arquivos de 01/08',
        ),
        findsOneWidget,
      );
      expect(find.text('Transferências entre suas contas'), findsOneWidget);
      expect(find.text('1 para confirmar · 2 já tratadas'), findsOneWidget);
      expect(
        find.text('${brl.format(1086.44)} a pagar · 1 compra'),
        findsOneWidget,
      );
      await _scrollTo(tester, find.text('Aberta'));
      expect(find.text('03/11 a 03/12 · aberta · até 14/11'), findsOneWidget);
      await _scrollTo(tester, find.text('Completo'));
      await _scrollTo(tester, find.text('Definir dono'));
      expect(find.text('Empresa'), findsOneWidget);
    });

    testWidgets('trocar o dono de uma conta chama a API', (tester) async {
      final api = _api()
        ..onAction = (_) => jsonResponse({
          ...accountsJson.last,
          'owner': 'empresa',
          'needs_owner': false,
        });
      await _open(tester, api, const TransactionsScreen());
      await _scrollTo(tester, find.text('Definir dono'));
      await tester.tap(find.text('Definir dono'));
      await tester.pumpAndSettle();
      await _tapAsync(tester, find.text('Nubank Empresas').last);
      final patch = api.requests.singleWhere((r) => r.method == 'PATCH');
      expect(patch.url.path, endsWith('/accounts/bb:70182-3'));
      expect(jsonDecode(bodyOf(patch)), {'owner': 'empresa'});
    });

    testWidgets('falha ao trocar o dono mostra aviso', (tester) async {
      final api = _api()..onAction = (_) => jsonResponse({'detail': 'x'}, 500);
      await _open(tester, api, const TransactionsScreen());
      await _scrollTo(tester, find.text('Definir dono'));
      await tester.tap(find.text('Definir dono'));
      await tester.pumpAndSettle();
      await _tapAsync(tester, find.text('Conta pessoal').last);
      expect(
        find.text('Não foi possível trocar o dono. Tente novamente.'),
        findsOneWidget,
      );
    });

    testWidgets('atalhos abrem transferências e parcelamentos', (tester) async {
      await _open(tester, _api(), const TransactionsScreen());
      await tester.tap(find.text('Transferências entre suas contas'));
      await tester.pumpAndSettle();
      expect(find.text('Transferências entre contas'), findsOneWidget);
      await tester.pageBack();
      await tester.pumpAndSettle();
      await tester.tap(find.text('Parcelamentos'));
      await tester.pumpAndSettle();
      expect(find.text('Em andamento'), findsOneWidget);
    });

    testWidgets('folha do arquivo marca a fatura como fechada', (tester) async {
      final api = _api();
      await _open(tester, api, const TransactionsScreen());
      await _scrollTo(tester, find.text('Aberta'));
      await tester.tap(find.text('Aberta'));
      await tester.pumpAndSettle();
      expect(find.text('Situação da fatura'), findsOneWidget);
      api.onAction = (_) => jsonResponse(
        statementsJson['statements'] is List
            ? (statementsJson['statements']! as List).first
            : {},
      );
      await _tapAsync(tester, find.text('Marcar como fechada'));
      final patch = api.requests.singleWhere((r) => r.method == 'PATCH');
      expect(patch.url.path, endsWith('/statements/s-aberta'));
      expect(jsonDecode(bodyOf(patch)), {'closed': true});
    });

    testWidgets('folha de um extrato completo permite reabrir', (tester) async {
      final api = _api();
      await _open(tester, api, const TransactionsScreen());
      await _scrollTo(tester, find.text('Completo'));
      await tester.tap(find.text('Completo'));
      await tester.pumpAndSettle();
      expect(find.text('Situação do extrato'), findsOneWidget);
      expect(find.text('Na verdade está incompleto'), findsOneWidget);
      expect(find.text('Configurar período'), findsOneWidget);
    });
  });
}
