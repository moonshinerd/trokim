import 'dart:convert';

import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:trokim/core/format.dart';
import 'package:trokim/core/settings/settings_controller.dart';
import 'package:trokim/features/categories/domain/categories.dart';
import 'package:trokim/features/categories/domain/ledger_entry.dart';
import 'package:trokim/features/categories/presentation/category_review_screen.dart';
import 'package:trokim/features/dashboard/presentation/dashboard_screen.dart';
import 'package:trokim/features/finance/domain/finance_models.dart';
import 'package:trokim/features/finance/presentation/finance_controller.dart';

import 'support/finance_fixtures.dart';
import 'support/flow_harness.dart';

Map<String, Object?> _tx(
  String uid,
  String merchant,
  double amount, {
  String category = 'outros',
  String nature = 'compra',
  String type = 'debit',
  String date = '2026-11-05',
  bool duplicate = false,
}) => {
  'uid': uid,
  'date': date,
  'amount': amount,
  'type': type,
  'category': category,
  'nature': nature,
  'merchant': merchant,
  'description': merchant,
  'source_file': 'fatura.ofx',
  'is_duplicate': duplicate,
};

final _ledger = <Map<String, Object?>>[
  _tx('u1', 'Eletro Exemplo', 271.61, date: '2026-11-07'),
  _tx('u2', 'Papelaria Exemplo', 64.9, date: '2026-10-25'),
  _tx('u3', 'Padaria Exemplo', 12.5, category: 'alimentacao'),
  // não entram na revisão: entrada, pagamento de fatura, transferência própria e duplicado
  _tx('u4', 'Cliente Exemplo', 2500, category: 'renda', type: 'credit'),
  _tx('u5', 'Pagamento da fatura', 250, nature: 'pagamento_fatura'),
  _tx('u6', 'Maria Exemplo', 300, nature: 'transferencia_propria'),
  _tx('u7', 'Eletro Exemplo', 271.61, duplicate: true),
];

Future<FakeFinanceApi> _open(
  WidgetTester tester, {
  Widget home = const CategoryReviewScreen(),
  List<Map<String, Object?>>? ledger,
}) async {
  final api = FakeFinanceApi(transactions: ledger ?? _ledger);
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
  await tester.runAsync(() async {
    await finance.load();
    await Future<void>.delayed(const Duration(milliseconds: 50));
  });
  await tester.pumpAndSettle();
  return api;
}

Future<void> _tapAsync(WidgetTester tester, Finder finder) async {
  await tester.runAsync(() async {
    await tester.tap(finder);
    await Future<void>.delayed(const Duration(milliseconds: 150));
  });
  await tester.pumpAndSettle();
}

void main() {
  group('LedgerEntry', () {
    test('lê o lançamento da API e ignora itens incompletos', () {
      final entries = LedgerEntry.listFromJson([
        _tx('a', 'Loja', -10),
        {'uid': 'b'},
        {'date': '2026-11-01', 'amount': 1},
      ]);
      expect(entries, hasLength(1));
      expect(entries.single.amount, 10);
      expect(entries.single.isDebit, isTrue);
    });

    test('só gastos de verdade podem ser recategorizados', () {
      final byUid = {
        for (final e in LedgerEntry.listFromJson(_ledger)) e.uid: e,
      };
      expect(byUid['u1']!.isEditableExpense, isTrue);
      for (final uid in ['u4', 'u5', 'u6', 'u7']) {
        expect(byUid[uid]!.isEditableExpense, isFalse, reason: uid);
      }
    });

    test('sem estabelecimento, o título é a descrição do banco', () {
      final entry = LedgerEntry.tryParse({
        ..._tx('a', '', 5),
        'description': 'Tarifa',
      })!;
      expect(entry.title, 'Tarifa');
    });

    test('a correção da API vira CategoryChange', () {
      final change = CategoryChange.fromJson({
        'updated': 3,
        'rule': true,
        'merchant': 'Loja',
      });
      expect(change.updated, 3);
      expect(change.rule, isTrue);
      expect(change.merchant, 'Loja');
    });
  });

  test('categoria desconhecida vira Outros e renda tem nome próprio', () {
    expect(categoryInfo('xyz').name, 'Outros');
    expect(categoryInfo('renda').name, 'Renda');
    expect(categoryInfo('alimentacao').name, 'Alimentação');
  });

  test('nome do banco a partir do identificador da API', () {
    expect(institutionName('bb'), 'Banco do Brasil');
    expect(institutionName('nubank'), 'Nubank');
    expect(institutionName('outro'), 'outro');
    expect(institutionName(null), isNull);
  });

  group('tela de categorias', () {
    testWidgets('abre nos gastos sem categoria e filtra todos os gastos', (
      tester,
    ) async {
      await _open(tester);
      expect(find.text('Sem categoria (2)'), findsOneWidget);
      expect(find.text('Eletro Exemplo'), findsOneWidget);
      expect(find.text('Papelaria Exemplo'), findsOneWidget);
      expect(find.text('Padaria Exemplo'), findsNothing);
      expect(find.text('Cliente Exemplo'), findsNothing);
      expect(find.text('Pagamento da fatura'), findsNothing);
      expect(find.text('Maria Exemplo'), findsNothing);
      await tester.tap(find.text('Todos os gastos'));
      await tester.pumpAndSettle();
      expect(find.text('Padaria Exemplo'), findsOneWidget);
      expect(find.text('05/11 · Alimentação'), findsOneWidget);
    });

    testWidgets('escolher a categoria vale para o estabelecimento todo', (
      tester,
    ) async {
      final api = await _open(tester);
      api.onCategory = (_) => jsonResponse({
        'updated': 2,
        'rule': true,
        'merchant': 'Eletro Exemplo',
      });
      await tester.tap(find.text('Eletro Exemplo'));
      await tester.pumpAndSettle();
      expect(find.text('Usar para tudo de Eletro Exemplo'), findsOneWidget);
      expect(find.text('07/11/2026 · ${brl.format(271.61)}'), findsOneWidget);
      await tester.tap(find.text('Moradia'));
      await tester.pumpAndSettle();
      await _tapAsync(tester, find.text('Salvar'));
      final patch = api.requests.singleWhere((r) => r.method == 'PATCH');
      expect(patch.url.path, endsWith('/transactions/u1/category'));
      expect(jsonDecode(bodyOf(patch)), {
        'category': 'moradia',
        'apply_to_merchant': true,
      });
      expect(find.text('2 lançamentos agora em Moradia.'), findsOneWidget);
      // o resumo e a lista são recarregados depois da correção
      expect(api.count('GET', '/transactions/summary'), 2);
    });

    testWidgets('desligar o interruptor muda só este lançamento', (
      tester,
    ) async {
      final api = await _open(tester);
      await tester.tap(find.text('Papelaria Exemplo'));
      await tester.pumpAndSettle();
      await tester.tap(find.byType(Switch));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Educação'));
      await tester.pumpAndSettle();
      await _tapAsync(tester, find.text('Salvar'));
      final patch = api.requests.singleWhere((r) => r.method == 'PATCH');
      expect(jsonDecode(bodyOf(patch))['apply_to_merchant'], isFalse);
      expect(find.text('Lançamento agora em Educação.'), findsOneWidget);
    });

    testWidgets('API recusando a correção mostra aviso', (tester) async {
      final api = await _open(tester);
      api.onCategory = (_) => jsonResponse({'detail': 'não'}, 400);
      await tester.tap(find.text('Eletro Exemplo'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Lazer e bem-estar'));
      await tester.pumpAndSettle();
      await _tapAsync(tester, find.text('Salvar'));
      expect(
        find.text('Não foi possível salvar. Tente novamente.'),
        findsOneWidget,
      );
    });

    testWidgets('fechar a folha sem salvar não chama a API', (tester) async {
      final api = await _open(tester);
      await tester.tap(find.text('Eletro Exemplo'));
      await tester.pumpAndSettle();
      await tester.tapAt(const Offset(10, 10));
      await tester.pumpAndSettle();
      expect(api.requests.where((r) => r.method == 'PATCH'), isEmpty);
    });

    testWidgets('tudo categorizado mostra mensagem', (tester) async {
      await _open(
        tester,
        ledger: [_tx('a', 'Padaria', 5, category: 'alimentacao')],
      );
      expect(
        find.text('Tudo categorizado. Nenhum gasto em "Outros".'),
        findsOneWidget,
      );
    });

    testWidgets('API fora do ar mostra erro e permite tentar de novo', (
      tester,
    ) async {
      final api = FakeFinanceApi(transactions: _ledger)..offline = true;
      final finance = api.controller();
      final settings = SettingsController.memory()..setReduceMotion(true);
      addTearDown(settings.dispose);
      addTearDown(finance.dispose);
      await tester.pumpWidget(
        SettingsScope(
          controller: settings,
          child: FinanceScope(
            controller: finance,
            child: const MaterialApp(home: CategoryReviewScreen()),
          ),
        ),
      );
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 50)),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('Não foi possível carregar'), findsOneWidget);
      api.offline = false;
      await _tapAsync(tester, find.text('Tentar de novo'));
      expect(find.text('Eletro Exemplo'), findsOneWidget);
    });
  });

  group('atalhos', () {
    testWidgets('tocar numa categoria do Resumo abre a revisão filtrada', (
      tester,
    ) async {
      await _open(tester, home: const DashboardScreen());
      await tester.ensureVisible(find.text('Alimentação'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Alimentação'));
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 100)),
      );
      await tester.pumpAndSettle();
      expect(find.text('Categorias dos gastos'), findsOneWidget);
      expect(find.text('Padaria Exemplo'), findsOneWidget);
      expect(find.text('Eletro Exemplo'), findsNothing);
    });

    testWidgets('o resumo da importação leva a categorizar os gastos', (
      tester,
    ) async {
      final h = FlowHarness();
      h.api.transactions = _ledger;
      h.api.onUpload = (_) =>
          jsonResponse({...uploadJson(), 'uncategorized_count': 2});
      await h.open(tester);
      await h.startImport(tester);
      await h.tapAsync(tester, find.text('Já tenho o arquivo'));
      expect(find.textContaining('2 gastos sem categoria'), findsOneWidget);
      await tester.ensureVisible(find.text('Categorizar agora'));
      await h.tapAsync(tester, find.text('Categorizar agora'));
      expect(find.text('Categorias dos gastos'), findsOneWidget);
      expect(find.text('Sem categoria (2)'), findsOneWidget);
    });
  });
}
