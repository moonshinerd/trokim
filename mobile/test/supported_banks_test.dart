import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:trokim/features/import_guide/domain/import_guides.dart';
import 'package:trokim/features/import_guide/presentation/import_flow_screen.dart';

import 'support/finance_fixtures.dart';
import 'support/flow_harness.dart';

Future<void> _advanceSteps(WidgetTester tester, int count) async {
  for (var i = 0; i < count; i++) {
    await tester.tap(find.text('Próximo'));
    await tester.pumpAndSettle();
  }
}

void main() {
  group('Domínio: supportedBanks e getGuideForBank', () {
    test('catálogo contém os 7 bancos obrigatórios e níveis corretos', () {
      expect(supportedBanks.length, 7);

      final bankMap = {for (final b in supportedBanks) b.bank: b};

      // Bancos Validados
      expect(bankMap[GuideBank.nubank]!.supportLevel, BankSupportLevel.validated);
      expect(bankMap[GuideBank.bb]!.supportLevel, BankSupportLevel.validated);
      expect(bankMap[GuideBank.picpay]!.supportLevel, BankSupportLevel.validated);
      expect(bankMap[GuideBank.mercadopago]!.supportLevel, BankSupportLevel.validated);

      // Bancos Experimentais
      expect(bankMap[GuideBank.inter]!.supportLevel, BankSupportLevel.experimental);
      expect(bankMap[GuideBank.c6]!.supportLevel, BankSupportLevel.experimental);
      expect(bankMap[GuideBank.itau]!.supportLevel, BankSupportLevel.experimental);

      // Nenhum banco experimental possui aviso vazio
      for (final bank in supportedBanks) {
        if (bank.isExperimental) {
          expect(bank.experimentalNotice, isNotNull);
          expect(bank.experimentalNotice, contains('não testado'));
        }
      }
    });

    test('getGuideForBank gera passos navegáveis para todos os bancos', () {
      for (final info in supportedBanks) {
        final cardSteps = getGuideForBank(info.bank, NubankStatementKind.card);
        final accSteps = getGuideForBank(info.bank, NubankStatementKind.account);

        expect(cardSteps, isNotEmpty, reason: 'Cartão de ${info.name}');
        expect(accSteps, isNotEmpty, reason: 'Conta de ${info.name}');

        for (final step in [...cardSteps, ...accSteps]) {
          expect(step.title, isNotEmpty);
          expect(step.description, isNotEmpty);
        }
      }
    });
  });

  group('Tela de Bancos Suportados (Widget)', () {
    testWidgets('exibe título, selos Validado e Experimental e formatos aceitos', (
      tester,
    ) async {
      final h = FlowHarness();
      await h.open(tester);
      await h.startImport(tester);

      expect(find.text('Bancos suportados'), findsOneWidget);
      expect(find.text('De qual banco é o arquivo?'), findsOneWidget);

      // Selos na tela
      expect(find.text('Validado'), findsAtLeastNWidgets(2));
      expect(find.text('Experimental'), findsAtLeastNWidgets(2));

      // Bancos validados visíveis
      expect(find.text('Nubank'), findsOneWidget);
      expect(find.text('Banco do Brasil'), findsOneWidget);
      expect(find.text('PicPay'), findsOneWidget);
      expect(find.text('Mercado Pago'), findsOneWidget);

      // Bancos experimentais na lista (com rolagem)
      await tester.scrollUntilVisible(find.text('Banco Inter'), 150);
      expect(find.text('Banco Inter'), findsOneWidget);

      await tester.scrollUntilVisible(find.text('C6 Bank'), 150);
      expect(find.text('C6 Bank'), findsOneWidget);

      await tester.scrollUntilVisible(find.text('Itaú'), 150);
      expect(find.text('Itaú'), findsOneWidget);

      // Atalhos
      await tester.scrollUntilVisible(find.text('Outro banco'), 150);
      expect(find.text('Outro banco'), findsOneWidget);
      expect(find.text('Banco não reconhecido?'), findsOneWidget);
      expect(find.text('Pedir suporte a um banco'), findsOneWidget);
      expect(find.text('Já tenho o arquivo'), findsOneWidget);
    });

    testWidgets('botão "Já tenho o arquivo" pula tutoriais e abre seletor', (
      tester,
    ) async {
      final h = FlowHarness();
      h.api.onUpload = (_) => jsonResponse(uploadJson());
      await h.open(tester);
      await h.startImport(tester);

      await h.tapAsync(tester, find.text('Já tenho o arquivo'));
      expect(find.text('Pronto!'), findsOneWidget);
    });

    testWidgets('opção "Outro banco" aciona a leitura sem tutorial', (
      tester,
    ) async {
      final h = FlowHarness();
      h.api.onUpload = (_) => jsonResponse(uploadJson(institution: 'outro'));
      await h.open(tester);
      await h.startImport(tester);

      await tester.scrollUntilVisible(find.text('Outro banco'), 200);
      await h.tapAsync(tester, find.text('Outro banco'));
      expect(find.text('Pronto!'), findsOneWidget);
    });

    testWidgets('link "Pedir suporte a um banco" aciona callback', (
      tester,
    ) async {
      var requested = false;
      final h = FlowHarness();
      await h.open(
        tester,
        home: Scaffold(
          body: ImportFlowScreen(
            onRequestSupport: () => requested = true,
          ),
        ),
      );

      await tester.scrollUntilVisible(find.text('Pedir suporte a um banco'), 250);
      await tester.tap(find.text('Pedir suporte a um banco'));
      await tester.pumpAndSettle();

      expect(requested, isTrue);
    });
  });

  group('Tutoriais por banco', () {
    testWidgets('PicPay (Validado): tutorial da fatura do cartão', (tester) async {
      final h = FlowHarness();
      await h.open(tester);
      await h.startImport(tester);

      // Toca no card do PicPay
      await tester.tap(find.text('PicPay'));
      await tester.pumpAndSettle();

      expect(find.text('O que você quer importar?'), findsOneWidget);
      expect(find.text('PicPay Card (arquivo PDF)'), findsOneWidget);

      await tester.tap(find.text('Fatura do cartão'));
      await tester.pumpAndSettle();

      // Passo 1
      expect(find.text('Passo 1 de 4'), findsOneWidget);
      expect(find.text('Abra o PicPay Card'), findsOneWidget);
      expect(find.text('Pular tutorial'), findsOneWidget);

      // Passo 2
      await tester.tap(find.text('Próximo'));
      await tester.pumpAndSettle();
      expect(find.text('Passo 2 de 4'), findsOneWidget);
      expect(find.text('Acesse a fatura fechada'), findsOneWidget);

      // Passo 3
      await tester.tap(find.text('Próximo'));
      await tester.pumpAndSettle();
      expect(find.text('Passo 3 de 4'), findsOneWidget);
      expect(find.text('Exporte em PDF'), findsOneWidget);

      // Passo 4 (último)
      await tester.tap(find.text('Próximo'));
      await tester.pumpAndSettle();
      expect(find.text('Passo 4 de 4'), findsOneWidget);
      expect(find.text('Compartilhe com o Trokim'), findsOneWidget);
      expect(find.text('Escolher arquivo'), findsOneWidget);
      expect(find.text('Não mostrar este tutorial de novo'), findsOneWidget);
      expect(find.text('Pular tutorial'), findsNothing);

      // Voltar
      await tester.tap(find.text('Voltar'));
      await tester.pumpAndSettle();
      expect(find.text('Passo 3 de 4'), findsOneWidget);
    });

    testWidgets('Mercado Pago (Validado): extrato da conta e pular tutorial', (
      tester,
    ) async {
      final h = FlowHarness();
      h.api.onUpload = (_) => jsonResponse(
        uploadJson(institution: 'mercadopago', kind: 'conta'),
      );
      await h.open(tester);
      await h.startImport(tester);

      await tester.tap(find.text('Mercado Pago'));
      await tester.pumpAndSettle();

      expect(find.text('O que você quer importar?'), findsOneWidget);
      expect(find.text('Extrato da conta Mercado Pago (arquivo PDF)'), findsOneWidget);

      await tester.tap(find.text('Extrato da conta'));
      await tester.pumpAndSettle();

      expect(find.text('Passo 1 de 4'), findsOneWidget);
      expect(find.text('Acesse seu extrato'), findsOneWidget);

      // Pular tutorial vai direto ao upload
      await h.tapAsync(tester, find.text('Pular tutorial'));
      expect(find.text('Pronto!'), findsOneWidget);
    });

    testWidgets('Banco Inter (Experimental): exibe selo e aviso experimental', (
      tester,
    ) async {
      final h = FlowHarness();
      await h.open(tester);
      await h.startImport(tester);

      await tester.scrollUntilVisible(find.text('Banco Inter'), 200);
      await tester.tap(find.text('Banco Inter'));
      await tester.pumpAndSettle();

      // Aviso experimental na tela de escolha do tipo
      expect(find.text('O que você quer importar?'), findsOneWidget);
      expect(
        find.textContaining('Suporte experimental: tutorial baseado na ajuda oficial'),
        findsOneWidget,
      );

      await tester.tap(find.text('Extrato da conta'));
      await tester.pumpAndSettle();

      // Aviso presente no tutorial
      expect(
        find.text('Banco experimental — ajuda oficial (não testado em conta real)'),
        findsOneWidget,
      );
      expect(find.text('Passo 1 de 4'), findsOneWidget);
      expect(find.text('Abra o extrato da conta'), findsOneWidget);

      await _advanceSteps(tester, 2);
      expect(find.text('Escolha período e formato OFX'), findsOneWidget);
    });

    testWidgets('C6 Bank (Experimental): fatura do cartão com passos curtos', (
      tester,
    ) async {
      final h = FlowHarness();
      await h.open(tester);
      await h.startImport(tester);

      await tester.scrollUntilVisible(find.text('C6 Bank'), 200);
      await tester.tap(find.text('C6 Bank'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Fatura do cartão'));
      await tester.pumpAndSettle();

      expect(find.text('Passo 1 de 4'), findsOneWidget);
      expect(find.text('Abra a área de cartões'), findsOneWidget);
      expect(
        find.text('Banco experimental — ajuda oficial (não testado em conta real)'),
        findsOneWidget,
      );

      await _advanceSteps(tester, 1);
      expect(find.text('Acesse a fatura fechada'), findsOneWidget);
    });

    testWidgets('Itaú (Experimental): extrato da conta em OFX', (tester) async {
      final h = FlowHarness();
      await h.open(tester);
      await h.startImport(tester);

      await tester.scrollUntilVisible(find.text('Itaú'), 200);
      await tester.tap(find.text('Itaú'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Extrato da conta'));
      await tester.pumpAndSettle();

      expect(find.text('Passo 1 de 4'), findsOneWidget);
      expect(find.text('Abra o extrato da conta'), findsOneWidget);

      await _advanceSteps(tester, 2);
      expect(find.text('Escolha o formato OFX'), findsOneWidget);
      expect(find.textContaining('Money 2000+'), findsOneWidget);
    });

    testWidgets('checkbox "Não mostrar este tutorial de novo" atualiza preferência', (
      tester,
    ) async {
      final h = FlowHarness();
      await h.open(tester);
      await h.startImport(tester);

      await tester.tap(find.text('PicPay'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Extrato da conta'));
      await tester.pumpAndSettle();

      await _advanceSteps(tester, 3);
      expect(find.text('Não mostrar este tutorial de novo'), findsOneWidget);

      // Marca o checkbox
      await tester.tap(find.text('Não mostrar este tutorial de novo'));
      await tester.pumpAndSettle();

      // Salva preferência ao escolher arquivo
      await h.tapAsync(tester, find.text('Escolher arquivo'));
      expect(h.settings.showImportTutorial, isFalse);
    });
  });
}

