import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:trokim/features/finance/domain/finance_models.dart';
import 'package:trokim/features/finance/presentation/finance_controller.dart';

import 'support/finance_fixtures.dart';

void main() {
  group('FinancialSummary', () {
    test('converte o JSON da API sem recalcular nada', () {
      final summary = FinancialSummary.fromJson({...summaryJson});
      expect(summary.totalIncome, 5000);
      expect(summary.totalExpenses, 2150.5);
      expect(summary.netBalance, 2849.5);
      expect(summary.expensesByCategory['moradia'], 1500);
      expect(summary.transactionCount, 5);
      expect(summary.isEmpty, isFalse);
      expect(summary.savingsFraction, closeTo(0.5699, 1e-9));
    });

    test('a taxa de poupança vira fração limitada entre 0 e 1', () {
      FinancialSummary withRate(double rate) =>
          FinancialSummary.fromJson({...summaryJson, 'savings_rate': rate});
      expect(withRate(150).savingsFraction, 1);
      expect(withRate(-20).savingsFraction, 0);
    });

    test('rejeita resposta com campos ausentes ou de tipo errado', () {
      expect(
        () =>
            FinancialSummary.fromJson({...summaryJson}..remove('net_balance')),
        throwsFormatException,
      );
      expect(
        () => FinancialSummary.fromJson({...summaryJson, 'total_income': '5'}),
        throwsFormatException,
      );
      expect(
        () => FinancialSummary.fromJson({
          ...summaryJson,
          'expenses_by_category': {'moradia': 'caro'},
        }),
        throwsFormatException,
      );
      expect(
        () => FinancialSummary.fromJson({
          ...summaryJson,
          'transaction_count': -1,
        }),
        throwsFormatException,
      );
    });
  });

  group('ImportedFile', () {
    test('agrupa por arquivo e separa as duplicatas', () {
      final files = ImportedFile.fromTransactions([
        for (final tx in transactionsJson) {...tx},
      ]);
      expect(files.map((f) => f.name), [
        'extrato_novembro.ofx',
        'fatura_cartao.pdf',
      ]);
      expect(files[0].imported, 2);
      expect(files[0].duplicates, 0);
      expect(files[0].kind, 'OFX');
      expect(files[1].imported, 1);
      expect(files[1].duplicates, 1);
      expect(files[1].kind, 'PDF');
    });

    test('documento confirmado não aparece como OFX', () {
      ImportedFile file(String name) =>
          ImportedFile(name: name, imported: 1, duplicates: 0);
      expect(file('documento lido por foto ou PDF').kind, 'Documento');
      expect(file('lançamento digitado na tela de documento').kind, 'Manual');
      expect(file('extrato.ofx').kind, 'OFX');
    });

    test('lançamento sem arquivo de origem não some da lista', () {
      final files = ImportedFile.fromTransactions([
        {'is_duplicate': false},
      ]);
      expect(files.single.name, 'arquivo desconhecido');
    });
  });

  group('FinanceController', () {
    test('carrega resumo e arquivos da API', () async {
      final api = FakeFinanceApi();
      final finance = api.controller();
      addTearDown(finance.dispose);
      expect(finance.status, FinanceStatus.idle);

      await finance.load();

      expect(finance.status, FinanceStatus.ready);
      expect(finance.summary!.netBalance, 2849.5);
      expect(finance.files.length, 2);
    });

    test(
      'API fora do ar vira estado de erro e dá para tentar de novo',
      () async {
        final api = FakeFinanceApi()..offline = true;
        final finance = api.controller();
        addTearDown(finance.dispose);

        await finance.load();
        expect(finance.status, FinanceStatus.error);
        expect(finance.summary, isNull);

        api.offline = false;
        await finance.load();
        expect(finance.status, FinanceStatus.ready);
      },
    );

    test('resposta inválida também vira erro, sem lançar', () async {
      final api = FakeFinanceApi(summary: {'oi': 1});
      final finance = api.controller();
      addTearDown(finance.dispose);
      await finance.load();
      expect(finance.status, FinanceStatus.error);
    });

    test('chamadas simultâneas compartilham a mesma requisição', () async {
      final api = FakeFinanceApi();
      final finance = api.controller();
      addTearDown(finance.dispose);

      await Future.wait([finance.load(), finance.load()]);

      expect(api.count('GET', '/transactions/summary'), 1);
    });

    test('importa o arquivo por multipart e recarrega o resumo', () async {
      final api = FakeFinanceApi();
      final finance = api.controller();
      addTearDown(finance.dispose);
      await finance.load();

      final result = await finance.importStatement(
        'novo.ofx',
        () async => utf8.encode('conteudo ofx sintetico'),
      );

      expect(result.filename, 'novo.ofx');
      expect(result.importedCount, 2);
      final upload = api.requests.singleWhere((r) => r.method == 'POST');
      expect(upload.headers['content-type'], startsWith('multipart/form-data'));
      final body = latin1.decode(upload.bodyBytes);
      expect(body, contains('filename="novo.ofx"'));
      expect(body, contains('conteudo ofx sintetico'));
      expect(api.count('GET', '/transactions/summary'), 2);
      expect(finance.importing, isFalse);
    });

    test('recusa formato não suportado sem chamar a API', () async {
      final api = FakeFinanceApi();
      final finance = api.controller();
      addTearDown(finance.dispose);

      await expectLater(
        finance.importStatement('foto.png', () async => [1]),
        throwsA(
          isA<ImportFailure>().having(
            (e) => e.message,
            'message',
            contains('.ofx'),
          ),
        ),
      );
      expect(api.requests, isEmpty);
    });

    test(
      'mostra a mensagem que a API devolveu quando ela recusa o arquivo',
      () async {
        final api = FakeFinanceApi()
          ..onUpload = (_) => jsonResponse({
            'detail': 'Erro ao processar arquivo OFX: arquivo vazio',
          }, 400);
        final finance = api.controller();
        addTearDown(finance.dispose);

        await expectLater(
          finance.importStatement('vazio.ofx', () async => [0]),
          throwsA(
            isA<ImportFailure>().having(
              (e) => e.message,
              'message',
              'Erro ao processar arquivo OFX: arquivo vazio',
            ),
          ),
        );
        expect(finance.importing, isFalse);
      },
    );

    test('falha de rede no envio orienta a conferir o endereço', () async {
      final api = FakeFinanceApi()..offline = true;
      final finance = api.controller();
      addTearDown(finance.dispose);

      await expectLater(
        finance.importStatement('extrato.pdf', () async => [0]),
        throwsA(
          isA<ImportFailure>().having(
            (e) => e.message,
            'message',
            contains('Ajustes'),
          ),
        ),
      );
      expect(finance.importing, isFalse);
    });

    test('erro HTTP sem detalhe cita o código', () async {
      final api = FakeFinanceApi()
        ..onUpload = (_) => http.Response('boom', 500);
      final finance = api.controller();
      addTearDown(finance.dispose);

      await expectLater(
        finance.importStatement('extrato.ofx', () async => [0]),
        throwsA(
          isA<ImportFailure>().having(
            (e) => e.message,
            'message',
            contains('500'),
          ),
        ),
      );
    });
  });

  test('nomes dos bancos do registro aparecem formatados', () {
    expect(institutionName('c6'), 'C6 Bank');
    expect(institutionName('mercadopago'), 'Mercado Pago');
    expect(institutionName('itau'), 'Itaú');
    expect(institutionName('desconhecido'), 'desconhecido');
  });
}
