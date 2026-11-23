import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:trokim/core/settings/settings_controller.dart';
import 'package:trokim/features/finance/presentation/finance_controller.dart';
import 'package:trokim/features/transactions/presentation/transactions_screen.dart';

import 'support/finance_fixtures.dart';

Map<String, Object?> _upload({
  String? institution = 'nubank',
  String? kind = 'cartao',
  int imported = 23,
  int duplicates = 0,
  int uncategorized = 9,
  Map<String, int> byNature = const {'compra': 21, 'pagamento_fatura': 1},
}) => {
  'filename': 'Nubank_2026-12-10.ofx',
  'imported_count': imported,
  'duplicate_count': duplicates,
  'institution': institution,
  'kind': kind,
  'uncategorized_count': uncategorized,
  'by_nature': byNature,
};

class _Harness {
  _Harness({this.tutorial = true, StatementPicker? picker})
    : picker =
          picker ??
          (() async =>
              PickedStatement('Nubank_2026-12-10.ofx', () async => [1]));

  final bool tutorial;
  final StatementPicker picker;
  final api = FakeFinanceApi(transactions: []);
  late final settings = SettingsController.memory()
    ..setReduceMotion(true)
    ..setShowImportTutorial(tutorial);
  late final FinanceController finance = api.controller();

  Future<void> open(WidgetTester tester) async {
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
    await tester.runAsync(finance.load);
    await tester.pump();
  }

  Future<void> tapAsync(WidgetTester tester, Finder finder) async {
    await tester.runAsync(() async {
      await tester.tap(finder);
      await Future<void>.delayed(const Duration(milliseconds: 100));
    });
    await tester.pumpAndSettle();
  }
}

void main() {
  testWidgets('tutorial do cartão: passo a passo até escolher o arquivo', (
    tester,
  ) async {
    final h = _Harness();
    h.api.onUpload = (_) => jsonResponse(_upload());
    await h.open(tester);

    await tester.tap(find.text('Importar extrato'));
    await tester.pumpAndSettle();
    expect(find.text('De qual banco é o arquivo?'), findsOneWidget);

    await tester.tap(find.text('Nubank'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Pessoa física'));
    await tester.pumpAndSettle();
    expect(find.text('Qual conta do Nubank?'), findsNothing);
    expect(find.text('O que você quer importar?'), findsOneWidget);

    await tester.tap(find.text('Fatura do cartão'));
    await tester.pumpAndSettle();
    expect(find.text('Abra a área do cartão'), findsOneWidget);
    expect(find.text('Passo 1 de 5'), findsOneWidget);

    for (final title in [
      'Acesse a fatura',
      'Toque em compartilhar',
      'Escolha o formato OFX',
      'Baixe o arquivo do e-mail',
    ]) {
      await tester.tap(find.text('Próximo'));
      await tester.pumpAndSettle();
      expect(find.text(title), findsOneWidget);
    }
    expect(find.text('Pular tutorial'), findsNothing); // último passo
    expect(find.text('Escolher arquivo'), findsOneWidget);

    await h.tapAsync(tester, find.text('Escolher arquivo'));
    expect(find.text('Pronto!'), findsOneWidget);
    expect(find.text('Detectei: Nubank, fatura do cartão'), findsOneWidget);
    expect(find.text('23 lançamentos lidos'), findsOneWidget);
    expect(
      find.textContaining('1 movimentação fora dos totais'),
      findsOneWidget,
    );
    expect(find.textContaining('9 gastos sem categoria'), findsOneWidget);
  });

  testWidgets('tutorial da conta tem 4 passos', (tester) async {
    final h = _Harness();
    await h.open(tester);
    await tester.tap(find.text('Importar extrato'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Nubank'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Pessoa física'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Extrato da conta'));
    await tester.pumpAndSettle();
    expect(find.text('Passo 1 de 4'), findsOneWidget);
    expect(find.text('Abra o saldo da conta'), findsOneWidget);
  });

  testWidgets('pular tutorial vai direto ao arquivo', (tester) async {
    final h = _Harness();
    h.api.onUpload = (_) => jsonResponse(_upload(kind: 'conta'));
    await h.open(tester);
    await tester.tap(find.text('Importar extrato'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Nubank'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Pessoa física'));
    await tester.pumpAndSettle();
    await h.tapAsync(tester, find.text('Pular tutorial'));
    expect(find.text('Pronto!'), findsOneWidget);
    expect(h.api.count('POST', '/transactions/upload'), 1);
  });

  testWidgets('"Já tenho o arquivo" abre o seletor sem tutorial', (
    tester,
  ) async {
    final h = _Harness();
    h.api.onUpload = (_) => jsonResponse(_upload());
    await h.open(tester);
    await tester.tap(find.text('Importar extrato'));
    await tester.pumpAndSettle();
    await h.tapAsync(tester, find.text('Já tenho o arquivo'));
    expect(find.text('Pronto!'), findsOneWidget);
  });

  testWidgets('"Outro banco" importa pelo caminho genérico', (tester) async {
    final h = _Harness();
    h.api.onUpload = (_) => jsonResponse(
      _upload(institution: null, kind: null, uncategorized: 0, byNature: {}),
    );
    await h.open(tester);
    await tester.tap(find.text('Importar extrato'));
    await tester.pumpAndSettle();
    await h.tapAsync(tester, find.text('Outro banco'));
    expect(find.text('Pronto!'), findsOneWidget);
    expect(find.textContaining('Detectei'), findsNothing);
  });

  testWidgets('"Não mostrar de novo" desliga o tutorial e vale na próxima', (
    tester,
  ) async {
    final h = _Harness();
    h.api.onUpload = (_) => jsonResponse(_upload());
    await h.open(tester);
    await tester.tap(find.text('Importar extrato'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Nubank'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Pessoa física'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Fatura do cartão'));
    await tester.pumpAndSettle();
    for (var i = 0; i < 4; i++) {
      await tester.tap(find.text('Próximo'));
      await tester.pumpAndSettle();
    }
    await tester.tap(find.text('Não mostrar este tutorial de novo'));
    await tester.pump();
    await h.tapAsync(tester, find.text('Escolher arquivo'));
    expect(h.settings.showImportTutorial, isFalse);
    await tester.tap(find.text('Concluir'));
    await tester.pumpAndSettle();

    // Próxima importação: abre o seletor direto, sem telas de tutorial.
    await h.tapAsync(tester, find.text('Importar extrato'));
    expect(find.text('De qual banco é o arquivo?'), findsNothing);
    expect(find.text('Pronto!'), findsOneWidget);
  });

  testWidgets('com o tutorial desligado em Ajustes, abre o seletor direto', (
    tester,
  ) async {
    final h = _Harness(tutorial: false);
    h.api.onUpload = (_) => jsonResponse(_upload());
    await h.open(tester);
    await h.tapAsync(tester, find.text('Importar extrato'));
    expect(find.text('De qual banco é o arquivo?'), findsNothing);
    expect(find.text('Pronto!'), findsOneWidget);
    expect(h.api.count('POST', '/transactions/upload'), 1);
  });

  testWidgets('cancelar o seletor com o tutorial desligado fecha o fluxo', (
    tester,
  ) async {
    final h = _Harness(tutorial: false, picker: () async => null);
    await h.open(tester);
    await h.tapAsync(tester, find.text('Importar extrato'));
    expect(find.text('Importar extrato'), findsOneWidget); // FAB, não a AppBar
    expect(find.text('Extratos e faturas'), findsOneWidget);
    expect(h.api.count('POST', '/transactions/upload'), 0);
  });

  testWidgets('voltar no tutorial retorna ao passo anterior', (tester) async {
    final h = _Harness();
    await h.open(tester);
    await tester.tap(find.text('Importar extrato'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Nubank'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Pessoa física'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Fatura do cartão'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Próximo'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Voltar'));
    await tester.pumpAndSettle();
    expect(find.text('Passo 1 de 5'), findsOneWidget);
    await tester.tap(find.text('Voltar'));
    await tester.pumpAndSettle();
    expect(find.text('O que você quer importar?'), findsOneWidget);
  });

  testWidgets('cancelar o seletor no fluxo não chama a API', (tester) async {
    final h = _Harness(picker: () async => null);
    await h.open(tester);
    await tester.tap(find.text('Importar extrato'));
    await tester.pumpAndSettle();
    await h.tapAsync(tester, find.text('Já tenho o arquivo'));
    expect(h.api.count('POST', '/transactions/upload'), 0);
    expect(find.text('De qual banco é o arquivo?'), findsOneWidget);
  });

  testWidgets('arquivo recusado mostra o motivo e permite tentar de novo', (
    tester,
  ) async {
    final h = _Harness();
    h.api.onUpload = (_) =>
        jsonResponse({'detail': 'Erro ao processar arquivo OFX: x'}, 400);
    await h.open(tester);
    await tester.tap(find.text('Importar extrato'));
    await tester.pumpAndSettle();
    await h.tapAsync(tester, find.text('Já tenho o arquivo'));
    expect(find.text('Não deu para importar'), findsOneWidget);
    await tester.tap(find.text('Ver tutorial'));
    await tester.pumpAndSettle();
    expect(find.text('De qual banco é o arquivo?'), findsOneWidget);
  });

  testWidgets('extensão não suportada é recusada com mensagem clara', (
    tester,
  ) async {
    final h = _Harness(
      picker: () async => PickedStatement('dados.csv', () async => [1]),
    );
    await h.open(tester);
    await tester.tap(find.text('Importar extrato'));
    await tester.pumpAndSettle();
    await h.tapAsync(tester, find.text('Já tenho o arquivo'));
    expect(
      find.text('Formato não suportado. Escolha um arquivo .ofx ou .pdf.'),
      findsOneWidget,
    );
    expect(h.api.count('POST', '/transactions/upload'), 0);
  });

  testWidgets('API fora do ar na importação mostra erro de conexão', (
    tester,
  ) async {
    final h = _Harness();
    await h.open(tester);
    h.api.offline = true;
    await tester.tap(find.text('Importar extrato'));
    await tester.pumpAndSettle();
    await h.tapAsync(tester, find.text('Já tenho o arquivo'));
    expect(
      find.textContaining('Confira o endereço em Ajustes'),
      findsOneWidget,
    );
  });

  testWidgets('repetidos ignorados aparecem no resumo', (tester) async {
    final h = _Harness();
    h.api.onUpload = (_) => jsonResponse(_upload(duplicates: 3, imported: 20));
    await h.open(tester);
    await tester.tap(find.text('Importar extrato'));
    await tester.pumpAndSettle();
    await h.tapAsync(tester, find.text('Já tenho o arquivo'));
    expect(find.textContaining('3 repetidos ignorados'), findsOneWidget);
  });
}
