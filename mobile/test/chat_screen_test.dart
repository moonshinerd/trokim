import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:material_ui/material_ui.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:trokim/core/network/api_client.dart';
import 'package:trokim/core/theme/app_theme.dart';
import 'package:trokim/features/chat_assistant/data/chat_repository.dart';
import 'package:trokim/features/chat_assistant/presentation/chat_controller.dart';
import 'package:trokim/features/chat_assistant/presentation/chat_screen.dart';

import 'support/abortable_client.dart';

const question = 'Como montar uma reserva de emergência?';
const answer = 'Priorize baixo risco e liquidez diária.';
const sourceUrl = 'https://www.gov.br/investidor/pt-br/reserva-de-emergencia';

http.Response reply({
  bool abstained = false,
  bool withUrl = true,
  String responseText = answer,
}) => http.Response.bytes(
  utf8.encode(
    jsonEncode({
      'query': question,
      'mode': 'grounded',
      'model': 'qwen2.5',
      'answered': !abstained,
      'status': abstained ? 'abstained' : 'grounded',
      'answer': abstained ? 'Não há evidências suficientes.' : responseText,
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
    }),
  ),
  200,
);

Future<void> openChat(
  WidgetTester tester,
  Future<http.Response> Function(http.Request) handler, {
  bool multiAgent = false,
}) async {
  final repository = ChatRepository(
    apiClient: ApiClient(client: abortableClient(handler)),
  );
  final controller = ChatController(
    repository: repository,
    multiAgent: multiAgent,
  );
  addTearDown(repository.close);
  addTearDown(controller.dispose);
  await tester.pumpWidget(
    MaterialApp(
      theme: AppTheme.lightTheme,
      home: ChatScreen(controller: controller),
    ),
  );
}

Future<void> sendQuestion(WidgetTester tester) async {
  await tester.enterText(find.byType(TextField), question);
  await tester.tap(find.byTooltip('Enviar'));
}

void main() {
  testWidgets('abre trilha e exibe cálculos da resposta multiagente', (
    tester,
  ) async {
    await openChat(
      tester,
      (_) async => http.Response.bytes(
        utf8.encode(
          jsonEncode({
            'query': question,
            'status': 'answered',
            'answer': answer,
            'model': 'qwen2.5',
            'evidences': [
              {
                'id': 'bcb-1',
                'source_name': 'BCB',
                'document_title': 'Caderno',
                'section': 'Planejamento',
                'content': 'Organize o orçamento.',
                'score': 0.9,
              },
            ],
            'calculations': [
              {
                'key': 'saldo',
                'label': 'Saldo do período',
                'value': 125.5,
                'unit': 'BRL',
                'source': 'CalculationService',
              },
            ],
            'validation_issues': [],
            'total_ms': 15,
            'steps': [
              {
                'agent': 'research',
                'status': 'ok',
                'summary': 'Fontes oficiais localizadas.',
                'duration_ms': 4,
              },
              {
                'agent': 'analysis',
                'status': 'skipped',
                'summary': 'Sem cálculo nesta pergunta.',
                'duration_ms': 0,
              },
              {
                'agent': 'communication',
                'status': 'ok',
                'summary': 'Resposta redigida.',
                'duration_ms': 7,
              },
              {
                'agent': 'validation',
                'status': 'ok',
                'summary': 'Resposta conferida.',
                'duration_ms': 4,
              },
            ],
          }),
        ),
        200,
      ),
      multiAgent: true,
    );
    await sendQuestion(tester);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Como cheguei a essa resposta'));
    await tester.pumpAndSettle();
    expect(find.text('Pesquisa'), findsOneWidget);
    expect(find.text('Validação'), findsOneWidget);
    expect(find.text('Fontes oficiais localizadas.\n4 ms'), findsOneWidget);
    expect(find.text('Saldo do período'), findsOneWidget);
    expect(find.text('R\$ 125,50'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  http.Response agentReply(
    String status, {
    String stepStatus = 'abstained',
    List<Map<String, Object>> issues = const [],
  }) => http.Response.bytes(
    utf8.encode(
      jsonEncode({
        'query': question,
        'status': status,
        'answer': 'Resposta de teste.',
        'evidences': [],
        'calculations': [],
        'validation_issues': issues,
        'total_ms': 3,
        'steps': [
          {
            'agent': status == 'rejected' ? 'validation' : 'research',
            'status': stepStatus,
            'summary': 'Resumo da etapa.',
            'duration_ms': 3,
          },
        ],
      }),
    ),
    200,
  );

  testWidgets('trilha explica abstenção em linguagem simples', (tester) async {
    await openChat(
      tester,
      (_) async => agentReply('abstained'),
      multiAgent: true,
    );
    await sendQuestion(tester);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Como cheguei a essa resposta'));
    await tester.pumpAndSettle();
    expect(
      find.text(
        'Não encontrei informações suficientes para responder com segurança.',
      ),
      findsOneWidget,
    );
    expect(
      tester.widget<Icon>(find.byIcon(Icons.info_outline)).semanticLabel,
      'Etapa sem informações suficientes',
    );
  });

  testWidgets('trilha explica rejeição e mostra o aviso de validação', (
    tester,
  ) async {
    await openChat(
      tester,
      (_) async => agentReply(
        'rejected',
        stepStatus: 'failed',
        issues: [
          {
            'code': 'NUMBER_NOT_SUPPORTED',
            'severity': 'blocker',
            'message': 'Um número da resposta não tem fonte.',
          },
        ],
      ),
      multiAgent: true,
    );
    await sendQuestion(tester);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Como cheguei a essa resposta'));
    await tester.pumpAndSettle();
    expect(
      find.text(
        'A resposta passou por uma checagem de segurança e não foi aprovada.',
      ),
      findsOneWidget,
    );
    expect(find.text('Um número da resposta não tem fonte.'), findsOneWidget);
  });

  testWidgets('falha de rede no modo multiagente mostra erro amigável', (
    tester,
  ) async {
    await openChat(
      tester,
      (_) async => throw const SocketException('sem rede'),
      multiAgent: true,
    );
    await sendQuestion(tester);
    await tester.pumpAndSettle();
    expect(find.textContaining('Não foi possível conectar'), findsWidgets);
    expect(find.text('Como cheguei a essa resposta'), findsNothing);
  });

  testWidgets('tentar novamente refaz a consulta multiagente após falha', (
    tester,
  ) async {
    var calls = 0;
    await openChat(tester, (_) async {
      calls++;
      if (calls == 1) throw const SocketException('sem rede');
      return agentReply('abstained');
    }, multiAgent: true);
    await sendQuestion(tester);
    await tester.pumpAndSettle();
    expect(find.text('Tentar novamente'), findsOneWidget);
    await tester.tap(find.text('Tentar novamente'));
    await tester.pumpAndSettle();
    expect(calls, 2);
    expect(find.text('Tentar novamente'), findsNothing);
    expect(find.text('Como cheguei a essa resposta'), findsOneWidget);
  });

  testWidgets(
    'preserva boas-vindas e mostra pergunta, resposta e card oficial',
    (tester) async {
      await openChat(tester, (_) async => reply());
      expect(
        find.textContaining('Olá! Sou o assistente do Trokim.'),
        findsOneWidget,
      );
      await sendQuestion(tester);
      await tester.pumpAndSettle();
      expect(find.text(question), findsOneWidget);
      expect(find.text(answer), findsOneWidget);
      expect(find.byType(Card), findsOneWidget);
      expect(
        find.text(
          'Comissão de Valores Mobiliários (CVM) • Reserva de emergência',
        ),
        findsOneWidget,
      );
      expect(find.text('Relevância 42%'), findsOneWidget);
      expect(find.text('SEÇÃO 1: Planejamento'), findsNothing);
      await tester.tap(
        find.text(
          'Comissão de Valores Mobiliários (CVM) • Reserva de emergência',
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('SEÇÃO 1: Planejamento'), findsOneWidget);
      expect(find.widgetWithText(SelectableText, sourceUrl), findsOneWidget);
      expect(
        tester.widget<TextField>(find.byType(TextField)).controller!.text,
        isEmpty,
      );
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'auditoria mostra comparação fundamentada sem inventar resposta',
    (tester) async {
      await openChat(tester, (_) async => reply());
      await sendQuestion(tester);
      await tester.pumpAndSettle();
      await tester.tap(find.byType(Switch));
      await tester.pumpAndSettle();

      expect(find.text('Comparativo de transparência'), findsOneWidget);
      expect(find.text('Com RAG'), findsOneWidget);
      expect(find.text('Sem lastro verificável'), findsOneWidget);
      expect(
        find.textContaining('Nenhuma resposta alternativa é apresentada'),
        findsOneWidget,
      );
    },
  );

  testWidgets('cartão de evidência abre a URL oficial no navegador', (
    tester,
  ) async {
    const channel = MethodChannel('plugins.flutter.io/url_launcher');
    final calls = <MethodCall>[];
    final messenger =
        TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
    messenger.setMockMethodCallHandler(channel, (call) async {
      calls.add(call);
      return true;
    });
    addTearDown(() => messenger.setMockMethodCallHandler(channel, null));

    await openChat(tester, (_) async => reply());
    await sendQuestion(tester);
    await tester.pumpAndSettle();
    await tester.tap(
      find.text(
        'Comissão de Valores Mobiliários (CVM) • Reserva de emergência',
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Abrir documento oficial'));
    await tester.pumpAndSettle();

    expect(calls.single.method, 'launch');
    expect((calls.single.arguments as Map)['url'], sourceUrl);
  });

  testWidgets('erro offline permite repetir sem duplicar a pergunta', (
    tester,
  ) async {
    var attempts = 0;
    await openChat(tester, (request) async {
      expect(jsonDecode(request.body), {
        'message': question,
        'mode': 'grounded',
      });
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

  testWidgets('abstenção tem aviso e não apresenta cards de fonte', (
    tester,
  ) async {
    await openChat(tester, (_) async => reply(abstained: true));
    await sendQuestion(tester);
    await tester.pumpAndSettle();
    expect(find.text('Não há evidências suficientes.'), findsOneWidget);
    expect(find.byIcon(Icons.warning_amber_rounded), findsOneWidget);
    expect(find.byType(Card), findsNothing);
    expect(find.text('Tentar novamente'), findsNothing);
  });

  testWidgets('abstenção oferece uma pergunta rápida permitida', (
    tester,
  ) async {
    final sentMessages = <String>[];
    var attempts = 0;
    await openChat(tester, (request) async {
      final message =
          (jsonDecode(request.body) as Map<String, dynamic>)['message']
              as String;
      sentMessages.add(message);
      attempts++;
      return attempts == 1 ? reply(abstained: true) : reply();
    });
    await sendQuestion(tester);
    await tester.pumpAndSettle();

    await tester.tap(find.text('Organizar o orçamento'));
    await tester.pumpAndSettle();

    expect(sentMessages.last, 'Como organizar meu orçamento mensal?');
    expect(find.text('Como organizar meu orçamento mensal?'), findsOneWidget);
    expect(attempts, 2);
  });

  testWidgets('carregamento indica consulta e impede outro envio', (
    tester,
  ) async {
    final pending = Completer<http.Response>();
    var requests = 0;
    await openChat(tester, (_) {
      requests++;
      return pending.future;
    });
    await sendQuestion(tester);
    await tester.pump();
    expect(
      find.text('Consultando fontes e gerando resposta...'),
      findsOneWidget,
    );
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(
      tester
          .widget<IconButton>(find.widgetWithIcon(IconButton, Icons.send))
          .onPressed,
      isNull,
    );
    expect(tester.widget<TextField>(find.byType(TextField)).enabled, isFalse);
    expect(requests, 1);
    pending.complete(reply());
    await tester.pumpAndSettle();
    expect(find.byType(CircularProgressIndicator), findsNothing);
    expect(
      tester
          .widget<IconButton>(find.widgetWithIcon(IconButton, Icons.send))
          .onPressed,
      isNotNull,
    );
  });

  testWidgets('fonte sem URL mantém card e não mostra texto nulo', (
    tester,
  ) async {
    await openChat(tester, (_) async => reply(withUrl: false));
    await sendQuestion(tester);
    await tester.pumpAndSettle();
    expect(find.byType(Card), findsOneWidget);
    expect(find.byType(SelectableText), findsNothing);
    expect(find.text('null'), findsNothing);
  });

  for (final size in [const Size(320, 640), const Size(800, 1280)]) {
    testWidgets('resposta longa e carregamento cabem em $size', (tester) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final pending = Completer<http.Response>();
      await openChat(tester, (_) => pending.future);
      await sendQuestion(tester);
      await tester.pump();
      expect(
        find.text('Consultando fontes e gerando resposta...'),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
      final longAnswer = List.filled(40, answer).join(' ');
      pending.complete(reply(responseText: longAnswer));
      await tester.pumpAndSettle();
      expect(find.text(longAnswer), findsOneWidget);
      expect(find.byType(Card), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('falha do modelo permite retry sem aviso de abstenção', (
    tester,
  ) async {
    var requests = 0;
    await openChat(tester, (request) async {
      expect(request.url.path, '/v1/chat/generate');
      expect((jsonDecode(request.body) as Map)['mode'], 'grounded');
      return ++requests == 1
          ? http.Response('Ollama indisponível', 500)
          : reply();
    });
    await sendQuestion(tester);
    await tester.pumpAndSettle();
    expect(find.text('Tentar novamente'), findsOneWidget);
    expect(find.text('Reserva de emergência'), findsNothing);
    expect(find.byType(Card), findsNothing);
    expect(find.textContaining('Ollama'), findsNothing);
    await tester.tap(find.text('Tentar novamente'));
    await tester.pumpAndSettle();
    expect(requests, 2);
    expect(find.text(question), findsOneWidget);
    expect(find.text(answer), findsOneWidget);
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

  testWidgets('tela estreita mantém resposta e fonte sem overflow', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(320, 640);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await openChat(tester, (_) async => reply());
    await sendQuestion(tester);
    await tester.pumpAndSettle();
    expect(find.byType(Card), findsOneWidget);
    expect(tester.takeException(), isNull);
    final scroll = tester
        .state<ScrollableState>(find.byType(Scrollable).first)
        .position;
    expect(scroll.pixels, closeTo(scroll.maxScrollExtent, 1));
  });
}
