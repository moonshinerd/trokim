import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:trokim/core/network/api_client.dart';
import 'package:trokim/features/chat_assistant/data/chat_repository.dart';
import 'package:trokim/features/chat_assistant/presentation/chat_controller.dart';
import 'package:trokim/features/chat_assistant/presentation/chat_screen.dart';

Map<String, dynamic> _evidence(int i) => {
      'id': 'e$i',
      'document_id': 'd$i',
      'source_name': 'Banco Central do Brasil',
      'source_url': 'https://www.bcb.gov.br/doc$i',
      'document_title': 'Documento $i',
      'section': 'SEÇÃO $i',
      'content': 'Conteúdo da fonte $i',
      'score': 0.8,
    };

Future<void> openChat(WidgetTester tester, String answer) async {
  final repo = ChatRepository(
    apiClient: ApiClient(
      client: MockClient(
        (_) async => http.Response.bytes(
          utf8.encode(jsonEncode({
            'answered': true,
            'status': 'grounded',
            'answer': answer,
            'evidences': [_evidence(1), _evidence(2)],
          })),
          200,
        ),
      ),
    ),
  );
  final chat = ChatController(repository: repo);
  addTearDown(repo.close);
  addTearDown(chat.dispose);
  await tester.pumpWidget(MaterialApp(home: ChatScreen(controller: chat)));
  await tester.enterText(find.byType(TextField), 'Como funciona?');
  await tester.tap(find.widgetWithIcon(IconButton, Icons.send));
  await tester.pumpAndSettle();
}

void main() {
  const answer =
      'Priorize baixo risco [1] e liquidez diária [2]. Veja também [3].\n\n'
      '**Fontes:**\n[1] BCB, Documento 1 https://www.bcb.gov.br/doc1\n'
      '[2] BCB, Documento 2 https://www.bcb.gov.br/doc2';

  testWidgets('o bloco de fontes com URLs não aparece no texto',
      (tester) async {
    await openChat(tester, answer);
    expect(find.textContaining('https://'), findsNothing);
    expect(find.textContaining('Fontes:'), findsNothing);
    expect(find.textContaining('Priorize baixo risco'), findsOneWidget);
  });

  testWidgets('tocar no [n] abre o cartão da fonte correspondente',
      (tester) async {
    await openChat(tester, answer);
    // cartões começam fechados
    expect(find.text('Conteúdo da fonte 1'), findsNothing);
    expect(find.text('Conteúdo da fonte 2'), findsNothing);

    await tester.tap(find.widgetWithText(InkWell, '2'));
    await tester.pumpAndSettle();
    expect(find.text('Conteúdo da fonte 2'), findsOneWidget);
    expect(find.text('Conteúdo da fonte 1'), findsNothing);

    await tester.tap(find.widgetWithText(InkWell, '1'));
    await tester.pumpAndSettle();
    expect(find.text('Conteúdo da fonte 1'), findsOneWidget);
  });

  testWidgets('marcador sem cartão correspondente fica só texto',
      (tester) async {
    await openChat(tester, answer);
    // [3] não tem cartão: não vira botão
    expect(find.widgetWithText(InkWell, '3'), findsNothing);
    expect(find.textContaining('[3]'), findsWidgets);
  });
}
