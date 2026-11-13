import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:trokim/core/network/api_client.dart';
import 'package:trokim/features/chat_assistant/data/chat_repository.dart';
import 'package:trokim/features/chat_assistant/data/conversation_store.dart';
import 'package:trokim/features/chat_assistant/domain/conversation.dart';
import 'package:trokim/features/chat_assistant/presentation/chat_controller.dart';
import 'package:trokim/features/chat_assistant/presentation/history_screen.dart';

http.Response _json(Map<String, dynamic> body) =>
    http.Response.bytes(utf8.encode(jsonEncode(body)), 200);

Map<String, dynamic> _evidence() => {
  'id': 'e1',
  'document_id': 'd1',
  'source_name': 'Banco Central do Brasil',
  'source_url': 'https://www.bcb.gov.br/doc',
  'document_title': 'Caderno de Educação Financeira',
  'section': 'SEÇÃO 1',
  'content': 'Conteúdo da fonte',
  'score': 0.8,
};

http.Response _reply([String answer = 'Resposta oficial [1]']) => _json({
  'query': 'pergunta',
  'mode': 'grounded',
  'answered': true,
  'status': 'grounded',
  'answer': answer,
  'model': 'ollama/gemma4:26b',
  'evidences': [_evidence()],
});

class Harness {
  Harness({
    String? title = 'Reserva de emergência',
    this.titleDelay = Duration.zero,
    ConversationStore? store,
    bool generative = true,
  }) : store = store ?? MemoryConversationStore(),
       _title = title {
    final client = MockClient((request) async {
      paths.add(request.url.path);
      if (request.url.path.endsWith('/chat/title')) {
        titleRequests++;
        if (titleDelay > Duration.zero) await Future<void>.delayed(titleDelay);
        final t = _title;
        return t == null ? http.Response('erro', 503) : _json({'title': t});
      }
      return _reply();
    });
    repository = ChatRepository(apiClient: ApiClient(client: client));
    controller = ChatController(
      repository: repository,
      store: this.store,
      generative: generative,
    );
  }

  final ConversationStore store;
  final Duration titleDelay;
  final String? _title;
  final List<String> paths = [];
  int titleRequests = 0;
  late final ChatRepository repository;
  late final ChatController controller;

  void dispose() {
    controller.dispose();
    repository.close();
  }
}

void main() {
  test('placeholderTitle encurta a pergunta sem cortar palavras', () {
    expect(
      placeholderTitle('Como montar uma reserva?'),
      'Como montar uma reserva?',
    );
    final long = placeholderTitle(
      'Como funciona a regra dos trinta dias do rotativo do cartão de crédito?',
    );
    expect(long.length, lessThanOrEqualTo(41));
    expect(long, endsWith('…'));
    expect(long, isNot(contains('  ')));
  });

  test(
    'título provisório (a pergunta) aparece na hora e o do LLM o substitui',
    () async {
      final h = Harness(titleDelay: const Duration(milliseconds: 80));
      addTearDown(h.dispose);

      final sending = h.controller.send('Quanto devo guardar por mês?');
      // logo após enviar: conversa criada com a pergunta como título provisório
      expect(h.controller.current?.title, 'Quanto devo guardar por mês?');
      expect(h.controller.current?.titleState, TitleState.placeholder);
      await sending;

      // resposta chegou; o nomeador está trabalhando
      expect(h.controller.current?.titleState, TitleState.generating);
      expect(h.controller.current?.title, 'Quanto devo guardar por mês?');

      await Future<void>.delayed(const Duration(milliseconds: 200));
      expect(h.controller.current?.title, 'Reserva de emergência');
      expect(h.controller.current?.titleState, TitleState.auto);
      expect(h.titleRequests, 1);
    },
  );

  test(
    'se o nomeador falhar, mantém o provisório e tenta de novo uma vez',
    () async {
      final h = Harness(title: null);
      addTearDown(h.dispose);

      await h.controller.send('Primeira pergunta');
      await Future<void>.delayed(const Duration(milliseconds: 50));
      expect(h.controller.current?.title, 'Primeira pergunta');
      expect(h.controller.current?.titleState, TitleState.placeholder);

      await h.controller.send('Segunda pergunta');
      await Future<void>.delayed(const Duration(milliseconds: 50));
      await h.controller.send('Terceira pergunta');
      await Future<void>.delayed(const Duration(milliseconds: 50));
      expect(h.titleRequests, 2, reason: 'no máximo 2 tentativas');
      expect(h.controller.current?.title, 'Primeira pergunta');
    },
  );

  test('renomear manualmente nunca é sobrescrito pelo LLM', () async {
    final h = Harness(titleDelay: const Duration(milliseconds: 80));
    addTearDown(h.dispose);

    await h.controller.send('Pergunta qualquer');
    final id = h.controller.current!.id;
    await h.controller.rename(id, '  Meu título  ');
    await Future<void>.delayed(const Duration(milliseconds: 200));

    expect(h.controller.current?.title, 'Meu título');
    expect(h.controller.current?.titleState, TitleState.manual);
  });

  test('conversas são guardadas, reabertas e apagadas', () async {
    final store = MemoryConversationStore();
    final h = Harness(store: store);
    addTearDown(h.dispose);
    await h.controller.send('Como organizar o orçamento?');
    await Future<void>.delayed(const Duration(milliseconds: 50));
    expect(store.saved, hasLength(1));
    expect(store.saved.single.messages.where((m) => m.isUser), hasLength(1));

    // novo "app": carrega do armazenamento
    final h2 = Harness(store: store);
    addTearDown(h2.dispose);
    await h2.controller.init();
    expect(h2.controller.conversations.single.title, 'Reserva de emergência');
    h2.controller.open(h2.controller.conversations.single.id);
    expect(
      h2.controller.messages.any(
        (m) => m.text == 'Como organizar o orçamento?',
      ),
      isTrue,
    );

    h2.controller.startNew();
    expect(h2.controller.current, isNull);
    expect(h2.controller.messages, hasLength(1));

    await h2.controller.delete(h2.controller.conversations.single.id);
    expect(h2.controller.conversations, isEmpty);
    expect(store.saved, isEmpty);
  });

  test(
    'o modo generativo usa /chat/generate e o extrativo, /chat/ask',
    () async {
      final ia = Harness();
      addTearDown(ia.dispose);
      await ia.controller.send('Pergunta');
      expect(ia.paths.first, endsWith('/chat/generate'));

      final ext = Harness(generative: false);
      addTearDown(ext.dispose);
      await ext.controller.send('Pergunta');
      expect(ext.paths.first, endsWith('/chat/ask'));
    },
  );

  test('uma resposta com abstenção não pede título ao LLM', () async {
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/chat/title')) {
        return _json({'title': 'X'});
      }
      return _json({
        'query': 'pergunta',
        'mode': 'grounded',
        'answered': false,
        'status': 'abstained',
        'answer': 'Sem evidências.',
        'model': 'ollama/gemma4:26b',
        'evidences': [],
      });
    });
    final repo = ChatRepository(apiClient: ApiClient(client: client));
    final c = ChatController(
      repository: repo,
      store: MemoryConversationStore(),
    );
    addTearDown(c.dispose);
    addTearDown(repo.close);
    await c.send('Qual ação comprar?');
    await Future<void>.delayed(const Duration(milliseconds: 30));
    expect(c.current?.titleState, TitleState.placeholder);
  });

  group('tela de histórico', () {
    Future<Harness> open(WidgetTester tester) async {
      final h = Harness();
      addTearDown(h.dispose);
      await h.controller.send('Como funciona o rotativo?');
      await tester.pumpWidget(
        MaterialApp(home: HistoryScreen(chat: h.controller)),
      );
      await tester.pumpAndSettle();
      return h;
    }

    testWidgets('lista a conversa com o título do LLM e a prévia', (
      tester,
    ) async {
      await open(tester);
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 60)),
      );
      await tester.pumpAndSettle();
      expect(find.text('Reserva de emergência'), findsOneWidget);
      expect(find.text('Como funciona o rotativo?'), findsOneWidget);
    });

    testWidgets('renomeia pelo menu', (tester) async {
      final h = await open(tester);
      await tester.tap(find.byTooltip('Opções da conversa'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Renomear'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), 'Meu rotativo');
      await tester.tap(find.text('Salvar'));
      await tester.pumpAndSettle();
      expect(h.controller.current?.title, 'Meu rotativo');
      expect(find.text('Meu rotativo'), findsOneWidget);
    });

    testWidgets('apagar pede confirmação', (tester) async {
      final h = await open(tester);
      await tester.tap(find.byTooltip('Opções da conversa'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Apagar'));
      await tester.pumpAndSettle();
      expect(find.text('Apagar conversa?'), findsOneWidget);

      await tester.tap(find.text('Cancelar'));
      await tester.pumpAndSettle();
      expect(h.controller.conversations, hasLength(1));

      await tester.tap(find.byTooltip('Opções da conversa'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Apagar'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Apagar'));
      await tester.pumpAndSettle();
      expect(h.controller.conversations, isEmpty);
      expect(find.text('Nenhuma conversa ainda'), findsOneWidget);
    });
  });
}
