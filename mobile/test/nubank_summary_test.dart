import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/intl.dart';
import 'package:trokim/core/settings/settings_controller.dart';
import 'package:trokim/features/dashboard/presentation/dashboard_screen.dart';
import 'package:trokim/features/finance/domain/finance_models.dart';
import 'package:trokim/features/finance/presentation/finance_controller.dart';

import 'support/finance_fixtures.dart';

final _brl = NumberFormat.currency(locale: 'pt_BR', symbol: 'R\$');

Map<String, Object?> _summary({
  int excluded = 0,
  Object? merchants = const <Object>[],
}) => {...summaryJson, 'excluded_count': excluded, 'top_merchants': merchants};

void main() {
  group('modelos', () {
    test('resumo antigo, sem os campos novos, continua válido', () {
      final summary = FinancialSummary.fromJson(summaryJson);
      expect(summary.excludedCount, 0);
      expect(summary.topMerchants, isEmpty);
    });

    test('lê estabelecimentos e movimentações fora dos totais', () {
      final summary = FinancialSummary.fromJson(
        _summary(
          excluded: 3,
          merchants: [
            {'merchant': 'Mercado Exemplo', 'total': 320.5},
            {'merchant': 'Padaria Exemplo', 'total': 60},
          ],
        ),
      );
      expect(summary.excludedCount, 3);
      expect(summary.topMerchants.map((m) => m.merchant), [
        'Mercado Exemplo',
        'Padaria Exemplo',
      ]);
      expect(summary.topMerchants.first.total, 320.5);
    });

    test('ignora estabelecimentos malformados sem quebrar', () {
      final summary = FinancialSummary.fromJson(
        _summary(
          merchants: [
            {'merchant': 'Ok', 'total': 1.5},
            {'merchant': 5, 'total': 1},
            {'merchant': 'Sem total'},
            'texto',
          ],
        ),
      );
      expect(summary.topMerchants.length, 1);
      expect(summary.topMerchants.single.merchant, 'Ok');
      expect(
        FinancialSummary.fromJson(_summary(merchants: 'x')).topMerchants,
        isEmpty,
      );
    });

    test(
      'resultado de importação traz banco, tipo e movimentações excluídas',
      () {
        final result = ImportResult.fromJson({
          'filename': 'a.ofx',
          'imported_count': 10,
          'duplicate_count': 2,
          'institution': 'nubank',
          'kind': 'conta',
          'uncategorized_count': 4,
          'by_nature': {
            'pix_enviado': 5,
            'pagamento_fatura': 1,
            'resgate_investimento': 2,
            'transferencia_propria': 1,
          },
        });
        expect(result.institutionLabel, 'Nubank');
        expect(result.kindLabel, 'extrato da conta');
        expect(result.excludedCount, 4);
        expect(result.duplicateCount, 2);
        expect(result.uncategorizedCount, 4);
      },
    );

    test('importação de API antiga (só filename e contagem) funciona', () {
      final result = ImportResult.fromJson({
        'filename': 'a.ofx',
        'imported_count': 2,
      });
      expect(result.institutionLabel, isNull);
      expect(result.kindLabel, isNull);
      expect(result.excludedCount, 0);
    });

    test('resposta de importação inválida é rejeitada', () {
      expect(
        () => ImportResult.fromJson({'imported_count': 1}),
        throwsFormatException,
      );
      expect(
        () => ImportResult.fromJson({'filename': 'a', 'imported_count': -1}),
        throwsFormatException,
      );
    });
  });

  group('Resumo', () {
    Future<void> open(WidgetTester tester, Map<String, Object?> summary) async {
      final api = FakeFinanceApi(summary: summary);
      final finance = api.controller();
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
      await tester.runAsync(finance.load);
      await tester.pump(const Duration(seconds: 2));
    }

    testWidgets('mostra onde mais gastou e o aviso de movimentações fora', (
      tester,
    ) async {
      await open(
        tester,
        _summary(
          excluded: 2,
          merchants: [
            {'merchant': 'Mercado Exemplo', 'total': 320.5},
            {'merchant': 'Padaria Exemplo', 'total': 60.0},
          ],
        ),
      );
      await tester.scrollUntilVisible(
        find.text('Onde você mais gastou'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Onde você mais gastou'), findsOneWidget);
      expect(find.text('Mercado Exemplo'), findsOneWidget);
      expect(find.text(_brl.format(320.5)), findsOneWidget);
      await tester.scrollUntilVisible(
        find.textContaining('2 movimentações ficaram fora dos totais'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      expect(
        find.textContaining('2 movimentações ficaram fora dos totais'),
        findsOneWidget,
      );
    });

    testWidgets('sem estabelecimentos nem exclusões, as seções não aparecem', (
      tester,
    ) async {
      await open(tester, _summary());
      expect(find.text('Onde você mais gastou'), findsNothing);
      expect(find.textContaining('fora dos totais'), findsNothing);
    });

    testWidgets('uma movimentação usa o singular', (tester) async {
      await open(tester, _summary(excluded: 1));
      await tester.scrollUntilVisible(
        find.textContaining('1 movimentação ficou fora dos totais'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      expect(
        find.textContaining('1 movimentação ficou fora dos totais'),
        findsOneWidget,
      );
    });
  });
}
