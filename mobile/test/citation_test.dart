import 'dart:convert';

import 'package:flutter/gestures.dart';
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

/// Toca no link de texto (o mesmo `onTap` que o gesto real dispara).
void tapLink(WidgetTester tester, String label) {
  var done = false;
  void visit(InlineSpan span) {
    if (span is! TextSpan || done) return;
    final rec = span.recognizer;
    if (span.text == label && rec is TapGestureRecognizer) {
      rec.onTap!();
      done = true;
      return;
    }
    span.children?.forEach(visit);
  }

  for (final r in tester.widgetList<RichText>(find.byType(RichText))) {
    visit(r.text);
  }
  expect(done, isTrue, reason: 'link "$label" não encontrado');
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
    expect(find.textContaining('Priorize baixo risco', findRichText: true),
        findsOneWidget);
    expect(find.textContaining('[1]', findRichText: true), findsNothing);
  });

  testWidgets('tocar no nome da fonte abre o cartão correspondente',
      (tester) async {
    await openChat(tester, answer);
    // cartões começam fechados
    expect(find.text('Conteúdo da fonte 1'), findsNothing);
    expect(find.text('Conteúdo da fonte 2'), findsNothing);

    tapLink(tester, 'BCB · Documento 2');
    await tester.pumpAndSettle();
    expect(find.text('Conteúdo da fonte 2'), findsOneWidget);
    expect(find.text('Conteúdo da fonte 1'), findsNothing);

    tapLink(tester, 'BCB · Documento 1');
    await tester.pumpAndSettle();
    expect(find.text('Conteúdo da fonte 1'), findsOneWidget);
  });

  testWidgets('marcador sem cartão correspondente fica só texto',
      (tester) async {
    await openChat(tester, answer);
    // [3] não tem cartão: não vira link, fica o texto original
    expect(find.textContaining('[3]', findRichText: true), findsOneWidget);
  });
}
