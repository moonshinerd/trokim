import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:trokim/core/network/api_client.dart';
import 'package:trokim/core/theme/app_theme.dart';
import 'package:trokim/features/chat_assistant/data/chat_repository.dart';
import 'package:trokim/features/chat_assistant/presentation/chat_controller.dart';
import 'package:trokim/features/chat_assistant/presentation/chat_screen.dart';

const question = 'Como montar uma reserva de emergência?';
const answer = 'Priorize baixo risco e liquidez diária.';
const sourceUrl = 'https://www.gov.br/investidor/pt-br/reserva-de-emergencia';

http.Response reply({bool abstained = false, bool withUrl = true}) => http.Response.bytes(
      utf8.encode(jsonEncode({
        'query': question,
        'answered': !abstained,
        'status': abstained ? 'abstained' : 'grounded',
        'answer': abstained ? 'Não há evidências suficientes.' : answer,
        'evidences': abstained
            ? []
            : [
                {
                  'id': 'cvm_emergencia.txt_1',
                  'source_name': 'Comissão de Valores Mobiliários (CVM)',
                  if (withUrl) 'source_url': sourceUrl,
                  'document_title': 'Reserva de emergência',
                  'section': 'SEÇÃO 1: Planejamento',
                  'content': answer,
                  'score': 0.42,
                },
              ],
      })),
      200,
    );

Future<void> openChat(
  WidgetTester tester,
  Future<http.Response> Function(http.Request) handler,
) async {
  final repository = ChatRepository(apiClient: ApiClient(client: MockClient(handler)));
  final controller = ChatController(repository: repository);
  addTearDown(repository.close);
  addTearDown(controller.dispose);
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.lightTheme,
    home: ChatScreen(controller: controller),
  ));
}

Future<void> sendQuestion(WidgetTester tester) async {
  await tester.enterText(find.byType(TextField), question);
  await tester.tap(find.byTooltip('Enviar'));
}

void main() {
  testWidgets('preserva boas-vindas e mostra pergunta, resposta e card oficial', (tester) async {
    await openChat(tester, (_) async => reply());
    expect(find.textContaining('Olá! Sou o assistente do Trokim.'), findsOneWidget);
    await sendQuestion(tester);
    await tester.pumpAndSettle();
    expect(find.text(question), findsOneWidget);
    expect(find.text(answer), findsOneWidget);
    expect(find.byType(Card), findsOneWidget);
    expect(
      find.text('Comissão de Valores Mobiliários (CVM) • Reserva de emergência'),
      findsOneWidget,
    );
    expect(find.text('SEÇÃO 1: Planejamento'), findsOneWidget);
    expect(find.widgetWithText(SelectableText, sourceUrl), findsOneWidget);
    expect(tester.widget<TextField>(find.byType(TextField)).controller!.text, isEmpty);
    expect(tester.takeException(), isNull);
  });

  testWidgets('erro offline permite repetir sem duplicar a pergunta', (tester) async {
    var attempts = 0;
    await openChat(tester, (request) async {
      expect(jsonDecode(request.body), {'message': question});
      if (++attempts == 1) throw const SocketException('Sem rede');
      return reply();
    });
    await sendQuestion(tester);
    await tester.pumpAndSettle();
    expect(find.text('Tentar novamente'), findsOneWidget);
    expect(find.byIcon(Icons.error_outline), findsOneWidget);
    await tester.tap(find.text('Tentar novamente'));
    await tester.pumpAndSettle();
    expect(attempts, 2);
    expect(find.text(question), findsOneWidget);
    expect(find.text(answer), findsOneWidget);
    expect(find.text('Tentar novamente'), findsNothing);
  });

  testWidgets('abstenção tem aviso e não apresenta cards de fonte', (tester) async {
    await openChat(tester, (_) async => reply(abstained: true));
    await sendQuestion(tester);
    await tester.pumpAndSettle();
    expect(find.text('Não há evidências suficientes.'), findsOneWidget);
    expect(find.byIcon(Icons.warning_amber_rounded), findsOneWidget);
    expect(find.byType(Card), findsNothing);
    expect(find.text('Tentar novamente'), findsNothing);
  });

  testWidgets('carregamento indica consulta e impede outro envio', (tester) async {
    final pending = Completer<http.Response>();
    var requests = 0;
    await openChat(tester, (_) {
      requests++;
      return pending.future;
    });
    await sendQuestion(tester);
    await tester.pump();
    expect(find.text('Consultando fontes oficiais...'), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(tester.widget<IconButton>(find.widgetWithIcon(IconButton, Icons.send)).onPressed, isNull);
    expect(tester.widget<TextField>(find.byType(TextField)).enabled, isFalse);
    expect(requests, 1);
    pending.complete(reply());
    await tester.pumpAndSettle();
    expect(find.byType(CircularProgressIndicator), findsNothing);
    expect(tester.widget<IconButton>(find.widgetWithIcon(IconButton, Icons.send)).onPressed, isNotNull);
  });

  testWidgets('fonte sem URL mantém card e não mostra texto nulo', (tester) async {
    await openChat(tester, (_) async => reply(withUrl: false));
    await sendQuestion(tester);
    await tester.pumpAndSettle();
    expect(find.byType(Card), findsOneWidget);
    expect(find.byType(SelectableText), findsNothing);
    expect(find.text('null'), findsNothing);
  });

  testWidgets('mensagem vazia não envia requisição', (tester) async {
    var requests = 0;
    await openChat(tester, (_) async {
      requests++;
      return reply();
    });
    await tester.enterText(find.byType(TextField), '   ');
    await tester.tap(find.byTooltip('Enviar'));
    await tester.pumpAndSettle();
    expect(requests, 0);
    expect(find.byType(Card), findsNothing);
  });

  testWidgets('tela estreita mantém resposta e fonte sem overflow', (tester) async {
    tester.view.physicalSize = const Size(320, 640);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await openChat(tester, (_) async => reply());
    await sendQuestion(tester);
    await tester.pumpAndSettle();
    expect(find.byType(Card), findsOneWidget);
    expect(tester.takeException(), isNull);
    final scroll = tester.state<ScrollableState>(find.byType(Scrollable).first).position;
    expect(scroll.pixels, closeTo(scroll.maxScrollExtent, 1));
  });
}
