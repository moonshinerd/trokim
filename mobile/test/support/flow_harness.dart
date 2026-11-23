import 'dart:convert';

import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:trokim/core/settings/settings_controller.dart';
import 'package:trokim/features/finance/presentation/finance_controller.dart';
import 'package:trokim/features/transactions/presentation/transactions_screen.dart';

import 'finance_fixtures.dart';

/// Inspeção devolvida pela API fake.
Map<String, Object?> inspection({
  String? institution = 'nubank',
  String? kind = 'conta',
  String? detectedOwner,
  String? confidence,
  bool needsOwner = false,
  bool hasConflict = false,
  List<Map<String, Object?>> warnings = const [],
  List<String> signals = const [],
  String status = 'fechada',
}) => {
  'filename': 'arquivo.ofx',
  'institution': institution,
  'kind': kind,
  'detected_owner': detectedOwner,
  'confidence': confidence,
  'needs_owner': needsOwner,
  'has_conflict': hasConflict,
  'warnings': warnings,
  'signals': [
    for (final label in signals)
      {
        'owner': detectedOwner,
        'source': 'x',
        'label': label,
        'strength': 'alta',
      },
  ],
  'period': {'status': status},
  'transaction_count': 3,
};

Map<String, Object?> warning(String code, String severity, String message) => {
  'code': code,
  'severity': severity,
  'message': message,
};

Map<String, Object?> statementJson({
  String status = 'aberta',
  String kind = 'cartao',
  bool confirmed = false,
  String id = 's1',
}) => {
  'id': id,
  'account_id': 'nubank:1',
  'filename': 'Nubank_2026-12-10.ofx',
  'kind': kind,
  'period_start': '2026-11-03',
  'period_end': '2026-12-03',
  'generated_at': '2026-11-18',
  'status': status,
  'covered_until': '2026-11-14',
  'closes_on': status == 'aberta' || status == 'parcial' ? '2026-12-03' : null,
  'user_confirmed': confirmed,
  'imported_count': 6,
};

Map<String, Object?> uploadJson({
  String outcome = 'novo',
  int delta = 0,
  Map<String, Object?>? statement,
  int suggestions = 0,
  int auto = 0,
  bool? reconciled,
  String institution = 'nubank',
  String kind = 'cartao',
  String filename = 'Nubank_2026-12-10.ofx',
  int imported = 6,
  int duplicates = 0,
}) => {
  'filename': filename,
  'imported_count': imported,
  'duplicate_count': duplicates,
  'institution': institution,
  'kind': kind,
  'outcome': outcome,
  'delta': delta,
  'reconciled': reconciled,
  'by_nature': {'compra': imported},
  'uncategorized_count': 0,
  'statement': statement,
  'account': {
    'id': 'nubank:1',
    'display_label': 'Nubank · cartão',
    'owner': 'pessoal',
    'kind': kind,
    'needs_owner': false,
  },
  'auto_transfers': auto,
  'transfer_suggestions': suggestions,
};

String bodyOf(http.Request request) => utf8.decode(request.bodyBytes);

bool hasField(http.Request request, String name, String value) {
  final body = bodyOf(request);
  return RegExp('name="$name"\\r?\\n\\r?\\n$value').hasMatch(body);
}

/// Monta o app de teste em torno da tela de Extratos, com a API falsa.
class FlowHarness {
  FlowHarness({this.tutorial = true, StatementPicker? picker, String? file})
    : picker =
          picker ??
          (() async => PickedStatement(
            file ?? 'Nubank_2026-12-10.ofx',
            () async => [1],
          ));

  final bool tutorial;
  final StatementPicker picker;
  final api = FakeFinanceApi(transactions: []);
  late final settings = SettingsController.memory()
    ..setReduceMotion(true)
    ..setShowImportTutorial(tutorial);
  late final FinanceController finance = api.controller();

  Future<void> open(WidgetTester tester, {Widget? home}) async {
    addTearDown(settings.dispose);
    addTearDown(finance.dispose);
    await tester.pumpWidget(
      SettingsScope(
        controller: settings,
        child: FinanceScope(
          controller: finance,
          child: MaterialApp(
            home: home ?? TransactionsScreen(pickFile: picker),
          ),
        ),
      ),
    );
    await tester.runAsync(finance.load);
    await tester.pump();
  }

  /// Toca e espera o que depende de rede/ações assíncronas (usa um relógio real curto).
  Future<void> tapAsync(WidgetTester tester, Finder finder) async {
    await tester.runAsync(() async {
      await tester.tap(finder);
      await Future<void>.delayed(const Duration(milliseconds: 150));
    });
    await tester.pumpAndSettle();
  }

  Future<void> startImport(WidgetTester tester) async {
    await tester.tap(find.text('Importar extrato'));
    await tester.pumpAndSettle();
  }
}
