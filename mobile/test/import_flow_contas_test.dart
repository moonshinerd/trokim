import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:trokim/features/import_guide/presentation/import_flow_screen.dart';
import 'package:trokim/features/transactions/presentation/transactions_screen.dart';

import 'support/finance_fixtures.dart';
import 'support/flow_harness.dart';

Future<void> _passos(WidgetTester tester, int proximos) async {
  for (var i = 0; i < proximos; i++) {
    await tester.tap(find.text('Próximo'));
    await tester.pumpAndSettle();
  }
}

void main() {
  group('tutoriais por banco', () {
    testWidgets('Banco do Brasil: fatura do cartão em PDF tem 4 passos', (
      tester,
    ) async {
      final h = FlowHarness(file: 'fatura.pdf');
      h.api.onUpload = (_) => jsonResponse(
        uploadJson(
          institution: 'bb',
          reconciled: true,
          filename: 'fatura.pdf',
          statement: statementJson(status: 'fechada'),
        ),
      );
      await h.open(tester);
      await h.startImport(tester);
      await tester.tap(find.text('Banco do Brasil'));
      await tester.pumpAndSettle();
      expect(find.text('O que você quer importar?'), findsOneWidget);
      expect(find.text('Cartão Ourocard (arquivo PDF)'), findsOneWidget);
      await tester.tap(find.text('Fatura do cartão'));
      await tester.pumpAndSettle();
      expect(find.text('Passo 1 de 4'), findsOneWidget);
      expect(find.text('Abra as faturas'), findsOneWidget);
      await _passos(tester, 2);
      expect(find.textContaining('sempre em PDF'), findsNothing);
      expect(find.textContaining('não existe OFX'), findsOneWidget);
      await _passos(tester, 1);
      expect(find.text('Compartilhe direto com o Trokim'), findsOneWidget);
      await h.tapAsync(tester, find.text('Escolher arquivo'));
      expect(find.text('Pronto!'), findsOneWidget);
      expect(
        find.text('O total da fatura bate com a soma dos lançamentos.'),
        findsOneWidget,
      );
      expect(find.text('Conta: Nubank · cartão'), findsOneWidget);
    });

    testWidgets('Banco do Brasil: extrato da conta em OFX tem 5 passos', (
      tester,
    ) async {
      final h = FlowHarness();
      await h.open(tester);
      await h.startImport(tester);
      await tester.tap(find.text('Banco do Brasil'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Extrato da conta'));
      await tester.pumpAndSettle();
      expect(find.text('Passo 1 de 5'), findsOneWidget);
      expect(find.text('Abra o extrato'), findsOneWidget);
      await _passos(tester, 3);
      expect(find.text('Escolha o tipo OFX'), findsOneWidget);
      expect(find.textContaining('Money 2000+'), findsOneWidget);
      await _passos(tester, 1);
      expect(find.text('Compartilhe com o Trokim'), findsOneWidget);
    });

    testWidgets('Nubank Empresas: conta tem 6 passos e avisa do PDF', (
      tester,
    ) async {
      final h = FlowHarness();
      await h.open(tester);
      await h.startImport(tester);
      await tester.tap(find.text('Nubank'));
      await tester.pumpAndSettle();
      expect(find.text('Qual conta do Nubank?'), findsOneWidget);
      await tester.tap(find.text('Nubank Empresas'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Extrato da conta'));
      await tester.pumpAndSettle();
      expect(find.text('Passo 1 de 6'), findsOneWidget);
      expect(find.text('Abra o saldo'), findsOneWidget);
      await _passos(tester, 1);
      expect(find.textContaining('Exportar agora'), findsOneWidget);
      await _passos(tester, 4);
      expect(find.text('Use o OFX que chega por e-mail'), findsOneWidget);
      expect(find.textContaining('sempre PDF'), findsOneWidget);
    });

    testWidgets('Nubank Empresas: cartão tem 5 passos', (tester) async {
      final h = FlowHarness();
      await h.open(tester);
      await h.startImport(tester);
      await tester.tap(find.text('Nubank'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Nubank Empresas'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Fatura do cartão'));
      await tester.pumpAndSettle();
      expect(find.text('Passo 1 de 5'), findsOneWidget);
      expect(find.textContaining('Nubank Empresas'), findsWidgets);
    });

    testWidgets('a conta escolhida no tutorial vai junto no envio', (
      tester,
    ) async {
      final h = FlowHarness();
      h.api.onUpload = (_) => jsonResponse(uploadJson());
      await h.open(tester);
      await h.startImport(tester);
      await tester.tap(find.text('Nubank'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Nubank Empresas'));
      await tester.pumpAndSettle();
      await h.tapAsync(tester, find.text('Pular tutorial'));
      final envio = h.api.requests.firstWhere(
        (r) =>
            r.method == 'POST' && r.url.path.endsWith('/transactions/upload'),
      );
      expect(hasField(envio, 'owner', 'empresa'), isTrue);
    });
  });

  group('detector antes de importar', () {
    testWidgets('sem saber o dono, pergunta e envia a escolha', (tester) async {
      final h = FlowHarness();
      h.api.onInspect = (_) => jsonResponse(inspection(needsOwner: true));
      h.api.onUpload = (_) => jsonResponse(uploadJson());
      await h.open(tester);
      await h.startImport(tester);
      await h.tapAsync(tester, find.text('Já tenho o arquivo'));
      expect(find.text('Essa conta é pessoal ou da empresa?'), findsOneWidget);
      expect(find.text('Detectei: Nubank, extrato da conta'), findsOneWidget);
      expect(h.api.count('POST', '/transactions/upload'), 0);
      await h.tapAsync(tester, find.text('Importar como Nubank Empresas'));
      expect(find.text('Pronto!'), findsOneWidget);
      final envio = h.api.requests.firstWhere(
        (r) => r.url.path.endsWith('/transactions/upload'),
      );
      expect(hasField(envio, 'owner', 'empresa'), isTrue);
    });

    testWidgets(
      'arquivo do Empresas enviado como pessoal: avisa e sugere o certo',
      (tester) async {
        final h = FlowHarness();
        h.api.onInspect = (_) => jsonResponse(
          inspection(
            detectedOwner: 'empresa',
            confidence: 'alta',
            hasConflict: true,
            signals: ['Esta conta já foi cadastrada como Nubank Empresas'],
            warnings: [
              warning(
                'dono_diferente_do_detectado',
                'conflito',
                'Você escolheu conta pessoal, mas este arquivo parece ser de Nubank Empresas.',
              ),
            ],
          ),
        );
        h.api.onUpload = (_) => jsonResponse(uploadJson());
        await h.open(tester);
        await h.startImport(tester);
        await tester.tap(find.text('Nubank'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Pessoa física'));
        await tester.pumpAndSettle();
        await h.tapAsync(tester, find.text('Pular tutorial'));
        expect(find.text('Confira antes de importar'), findsOneWidget);
        expect(
          find.textContaining('parece ser de Nubank Empresas'),
          findsOneWidget,
        );
        expect(find.textContaining('Como descobri'), findsOneWidget);
        expect(h.api.count('POST', '/transactions/upload'), 0);
        await h.tapAsync(tester, find.text('Importar como Nubank Empresas'));
        expect(find.text('Pronto!'), findsOneWidget);
        final envio = h.api.requests.firstWhere(
          (r) => r.url.path.endsWith('/transactions/upload'),
        );
        expect(hasField(envio, 'owner', 'empresa'), isTrue);
        expect(hasField(envio, 'confirmed', 'true'), isTrue);
      },
    );

    testWidgets('o usuário pode manter a escolha mesmo com o aviso', (
      tester,
    ) async {
      final h = FlowHarness();
      h.api.onInspect = (_) => jsonResponse(
        inspection(
          detectedOwner: 'empresa',
          confidence: 'media',
          warnings: [
            warning(
              'dono_diferente_do_detectado',
              'atencao',
              'O nome parece do Empresas.',
            ),
          ],
        ),
      );
      h.api.onUpload = (_) => jsonResponse(uploadJson());
      await h.open(tester);
      await h.startImport(tester);
      await tester.tap(find.text('Nubank'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Pessoa física'));
      await tester.pumpAndSettle();
      await h.tapAsync(tester, find.text('Pular tutorial'));
      await h.tapAsync(tester, find.text('Importar como Conta pessoal'));
      final envio = h.api.requests.firstWhere(
        (r) => r.url.path.endsWith('/transactions/upload'),
      );
      expect(hasField(envio, 'owner', 'pessoal'), isTrue);
    });

    testWidgets(
      'tipo diferente do escolhido: importar mesmo assim ou trocar o arquivo',
      (tester) async {
        var inspecoes = 0;
        final h = FlowHarness();
        h.api.onInspect = (_) {
          inspecoes++;
          return jsonResponse(
            inspection(
              kind: 'cartao',
              hasConflict: true,
              warnings: [
                warning(
                  'tipo_diferente',
                  'conflito',
                  'Você escolheu extrato da conta, mas o arquivo é uma fatura do cartão.',
                ),
              ],
            ),
          );
        };
        h.api.onUpload = (_) => jsonResponse(uploadJson());
        await h.open(tester);
        await h.startImport(tester);
        await tester.tap(find.text('Nubank'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Pessoa física'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Extrato da conta'));
        await tester.pumpAndSettle();
        await h.tapAsync(tester, find.text('Pular tutorial'));
        expect(find.textContaining('é uma fatura do cartão'), findsOneWidget);
        expect(find.text('Importar mesmo assim'), findsOneWidget);
        await h.tapAsync(tester, find.text('Escolher outro arquivo'));
        expect(inspecoes, 2); // escolheu de novo e leu outra vez
        expect(h.api.count('POST', '/transactions/upload'), 0);
      },
    );

    testWidgets('dono detectado sem conflito entra direto, sem perguntar', (
      tester,
    ) async {
      final h = FlowHarness();
      h.api.onInspect = (_) => jsonResponse(
        inspection(detectedOwner: 'empresa', confidence: 'media'),
      );
      h.api.onUpload = (_) => jsonResponse(uploadJson());
      await h.open(tester);
      await h.startImport(tester);
      await h.tapAsync(tester, find.text('Já tenho o arquivo'));
      expect(find.text('Pronto!'), findsOneWidget);
      final envio = h.api.requests.firstWhere(
        (r) => r.url.path.endsWith('/transactions/upload'),
      );
      expect(hasField(envio, 'owner', 'empresa'), isTrue);
    });

    testWidgets(
      'arquivo já importado em outra conta: avisa antes de importar',
      (tester) async {
        final h = FlowHarness();
        h.api.onInspect = (_) => jsonResponse(
          inspection(
            warnings: [
              warning(
                'ja_importado_em_outra_conta',
                'atencao',
                'Quase todos os lançamentos deste arquivo já foram importados em Nubank · conta.',
              ),
            ],
          ),
        );
        await h.open(tester);
        await h.startImport(tester);
        await h.tapAsync(tester, find.text('Já tenho o arquivo'));
        expect(find.textContaining('já foram importados em'), findsOneWidget);
        expect(find.text('Importar mesmo assim'), findsOneWidget);
      },
    );

    testWidgets('a API barrando por conflito (409) mostra o motivo', (
      tester,
    ) async {
      final h = FlowHarness();
      h.api.onUpload = (_) => jsonResponse({
        'detail': 'Você escolheu conta pessoal, mas este arquivo parece ser de Nubank Empresas. Confirme para importar mesmo assim.',
      }, 409);
      await h.open(tester);
      await h.startImport(tester);
      await h.tapAsync(tester, find.text('Já tenho o arquivo'));
      expect(find.text('Não deu para importar'), findsOneWidget);
      expect(
        find.textContaining('parece ser de Nubank Empresas'),
        findsOneWidget,
      );
    });

    testWidgets('arquivo compartilhado entra direto na leitura', (
      tester,
    ) async {
      final h = FlowHarness();
      h.api.onUpload = (_) => jsonResponse(uploadJson());
      await h.open(
        tester,
        home: ImportFlowScreen(
          initialFile: PickedStatement(
            'Nubank_2026-12-10.ofx',
            () async => [1],
          ),
        ),
      );
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 150)),
      );
      await tester.pumpAndSettle();
      expect(find.text('De qual banco é o arquivo?'), findsNothing);
      expect(find.text('Pronto!'), findsOneWidget);
    });
  });

  group('situação do período no resumo', () {
    testWidgets('fatura aberta: pergunta se já fechou e confirma', (
      tester,
    ) async {
      final h = FlowHarness();
      h.api.onUpload = (_) =>
          jsonResponse(uploadJson(statement: statementJson(status: 'aberta')));
      h.api.onAction = (_) =>
          jsonResponse(statementJson(status: 'fechada', confirmed: true));
      await h.open(tester);
      await h.startImport(tester);
      await h.tapAsync(tester, find.text('Já tenho o arquivo'));
      expect(
        find.text('Fatura aberta · 03/11/2026 a 03/12/2026'),
        findsOneWidget,
      );
      expect(find.textContaining('fecha em 03/12/2026'), findsOneWidget);
      expect(find.textContaining('vão até 14/11'), findsOneWidget);
      await h.tapAsync(tester, find.text('Já fechou'));
      final patch = h.api.requests.firstWhere((r) => r.method == 'PATCH');
      expect(patch.url.path, endsWith('/statements/s1'));
      expect(jsonDecode(patch.body), {'closed': true});
      expect(find.text('Anotado: esta fatura está completa.'), findsNothing);
      expect(find.text('Anotado: esta fatura está completo.'), findsOneWidget);
    });

    testWidgets('fatura aberta: confirmar que ainda está aberta', (
      tester,
    ) async {
      final h = FlowHarness();
      h.api.onUpload = (_) =>
          jsonResponse(uploadJson(statement: statementJson(status: 'aberta')));
      h.api.onAction = (_) =>
          jsonResponse(statementJson(status: 'aberta', confirmed: true));
      await h.open(tester);
      await h.startImport(tester);
      await h.tapAsync(tester, find.text('Já tenho o arquivo'));
      await h.tapAsync(tester, find.text('Ainda está aberta'));
      final patch = h.api.requests.firstWhere((r) => r.method == 'PATCH');
      expect(jsonDecode(patch.body), {'closed': false});
      expect(
        find.textContaining('Importe de novo quando fechar'),
        findsOneWidget,
      );
    });

    testWidgets('extrato parcial usa o vocabulário de extrato', (tester) async {
      final h = FlowHarness();
      h.api.onUpload = (_) => jsonResponse(
        uploadJson(
          kind: 'conta',
          statement: statementJson(status: 'parcial', kind: 'conta'),
        ),
      );
      await h.open(tester);
      await h.startImport(tester);
      await h.tapAsync(tester, find.text('Já tenho o arquivo'));
      expect(find.textContaining('Extrato parcial'), findsOneWidget);
      expect(find.textContaining('Ele já está completo?'), findsOneWidget);
      expect(find.text('Está completo'), findsOneWidget);
      expect(find.text('Ainda não'), findsOneWidget);
    });

    testWidgets('situação desconhecida pergunta se o período está completo', (
      tester,
    ) async {
      final h = FlowHarness();
      h.api.onUpload = (_) => jsonResponse(
        uploadJson(statement: statementJson(status: 'desconhecida')),
      );
      await h.open(tester);
      await h.startImport(tester);
      await h.tapAsync(tester, find.text('Já tenho o arquivo'));
      expect(
        find.textContaining('Não consegui saber se esta fatura'),
        findsOneWidget,
      );
    });

    testWidgets('fatura fechada não faz pergunta', (tester) async {
      final h = FlowHarness();
      h.api.onUpload = (_) =>
          jsonResponse(uploadJson(statement: statementJson(status: 'fechada')));
      await h.open(tester);
      await h.startImport(tester);
      await h.tapAsync(tester, find.text('Já tenho o arquivo'));
      expect(
        find.textContaining('Fatura fechada · 03/11/2026'),
        findsOneWidget,
      );
      expect(find.text('Já fechou'), findsNothing);
    });

    testWidgets('configurar o período abre o seletor de datas', (tester) async {
      final h = FlowHarness();
      h.api.onUpload = (_) =>
          jsonResponse(uploadJson(statement: statementJson(status: 'aberta')));
      await h.open(tester);
      await h.startImport(tester);
      await h.tapAsync(tester, find.text('Já tenho o arquivo'));
      await tester.ensureVisible(find.text('Configurar período'));
      await tester.tap(find.text('Configurar período'));
      await tester.pumpAndSettle();
      expect(find.text('Período do arquivo'), findsOneWidget);
    });

    testWidgets(
      'erro ao salvar a confirmação mostra aviso e mantém a pergunta',
      (tester) async {
        final h = FlowHarness();
        h.api.onUpload = (_) => jsonResponse(
          uploadJson(statement: statementJson(status: 'aberta')),
        );
        h.api.onAction = (_) => http.Response('erro', 500);
        await h.open(tester);
        await h.startImport(tester);
        await h.tapAsync(tester, find.text('Já tenho o arquivo'));
        await h.tapAsync(tester, find.text('Já fechou'));
        expect(
          find.text('Não foi possível salvar. Tente novamente.'),
          findsOneWidget,
        );
        expect(find.text('Já fechou'), findsOneWidget);
      },
    );
  });

  group('mensagens do resumo', () {
    testWidgets('arquivo atualizado mostra quantos lançamentos entraram', (
      tester,
    ) async {
      final h = FlowHarness();
      h.api.onUpload = (_) =>
          jsonResponse(uploadJson(outcome: 'atualizado', delta: 3));
      await h.open(tester);
      await h.startImport(tester);
      await h.tapAsync(tester, find.text('Já tenho o arquivo'));
      expect(
        find.text('Atualizei o arquivo deste período (+3 lançamentos).'),
        findsOneWidget,
      );
    });

    testWidgets('arquivo repetido avisa que nada mudou', (tester) async {
      final h = FlowHarness();
      h.api.onUpload = (_) =>
          jsonResponse(uploadJson(outcome: 'repetido', duplicates: 6));
      await h.open(tester);
      await h.startImport(tester);
      await h.tapAsync(tester, find.text('Já tenho o arquivo'));
      expect(
        find.text('Este arquivo já estava importado: nada mudou.'),
        findsOneWidget,
      );
      expect(find.textContaining('repetidos ignorados'), findsNothing);
    });

    testWidgets('total que não bate com o do PDF é sinalizado', (tester) async {
      final h = FlowHarness(file: 'fatura.pdf');
      h.api.onUpload = (_) =>
          jsonResponse(uploadJson(reconciled: false, institution: 'bb'));
      await h.open(tester);
      await h.startImport(tester);
      await h.tapAsync(tester, find.text('Já tenho o arquivo'));
      expect(find.textContaining('não bate com a soma'), findsOneWidget);
    });

    testWidgets('transferências reconhecidas e sugeridas aparecem no resumo', (
      tester,
    ) async {
      final h = FlowHarness();
      h.api.suggestions = [
        {
          'id': 't1',
          'kind': 'transferencia',
          'debit_uid': 'd1',
          'credit_uid': 'c1',
          'amount': 308.76,
          'debit_date': '2026-10-05',
          'credit_date': '2026-10-05',
          'from_label': 'Nubank · conta',
          'to_label': 'Nubank Empresas · conta',
          'confidence': 'alta',
          'reason': 'Mesmo valor e mesma data.',
        },
      ];
      h.api.onUpload = (_) => jsonResponse(uploadJson(auto: 2, suggestions: 1));
      await h.open(tester);
      await h.startImport(tester);
      await h.tapAsync(tester, find.text('Já tenho o arquivo'));
      expect(
        find.text(
          'Reconheci 2 transferências entre suas contas e deixei fora dos totais.',
        ),
        findsOneWidget,
      );
      expect(find.textContaining('1 possível transferência'), findsOneWidget);
      await tester.ensureVisible(find.text('Revisar agora'));
      await tester.tap(find.text('Revisar agora'));
      await tester.pumpAndSettle();
      expect(find.text('Para confirmar'), findsOneWidget);
      expect(find.text('R\$ 308,76'), findsOneWidget);
    });
  });
}
