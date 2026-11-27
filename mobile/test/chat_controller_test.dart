import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:trokim/core/network/api_client.dart';
import 'package:trokim/features/chat_assistant/data/chat_repository.dart';
import 'package:trokim/features/chat_assistant/domain/chat_models.dart';
import 'package:trokim/features/chat_assistant/presentation/chat_controller.dart';

import 'support/abortable_client.dart';

void main() {
  ChatController controllerFor(
    Future<http.Response> Function(http.Request) handler,
  ) {
    final repository = ChatRepository(
      apiClient: ApiClient(client: MockClient(handler)),
    );
    final controller = ChatController(repository: repository);
    addTearDown(repository.close);
    addTearDown(controller.dispose);
    return controller;
  }

  http.Response response({bool answered = true}) => http.Response.bytes(
    utf8.encode(
      jsonEncode(<String, dynamic>{
        'query': 'Como criar uma reserva?',
        'mode': 'grounded',
        'model': 'qwen2.5',
        'answered': answered,
        'status': answered ? 'grounded' : 'abstained',
        'answer': answered
            ? 'Resposta oficial'
            : 'Não há evidências suficientes.',
        'evidences': answered
            ? [
                {
                  'id': 'cvm_reserva_1',
                  'source_name': 'CVM',
                  'document_title': 'Reserva de emergência',
                  'section': 'Planejamento',
                  'content': 'Mantenha uma reserva.',
                  'score': 0.42,
                },
              ]
            : [],
      }),
    ),
    200,
  );

  test('preserva boas-vindas e expõe lista imutável', () {
    final controller = controllerFor((_) async => response());
    expect(
      controller.messages.single.text,
      startsWith('Olá! Sou o assistente do Trokim.'),
    );
    expect(controller.messages.single.isUser, isFalse);
    expect(controller.isLoading, isFalse);
    expect(() => controller.messages.clear(), throwsUnsupportedError);
  });

  test('ignora vazio e envio concorrente enquanto aguarda resposta', () async {
    final pending = Completer<http.Response>();
    var calls = 0;
    final controller = controllerFor((request) {
      calls++;
      expect(jsonDecode(request.body), {
        'message': 'Reserva?',
        'mode': 'grounded',
      });
      return pending.future;
    });
    await controller.send('   ');
    expect(calls, 0);
    final sending = controller.send('  Reserva?  ');
    expect(controller.isLoading, isTrue);
    expect(controller.messages.last.text, 'Reserva?');
    expect(controller.messages.last.isUser, isTrue);
    await controller.send('Outra pergunta');
    await controller.retry();
    expect(controller.messages.length, 2);
    pending.complete(response());
    await sending;
    expect(calls, 1);
    expect(controller.isLoading, isFalse);
    expect(controller.messages.last.text, 'Resposta oficial');
    expect(controller.messages.last.isError, isFalse);
  });

  test('retry repete última pergunta com erro sem duplicar usuário', () async {
    final questions = <String>[];
    final controller = controllerFor((request) async {
      questions.add((jsonDecode(request.body) as Map)['message'] as String);
      return questions.length == 1 ? http.Response('', 500) : response();
    });
    await controller.retry();
    expect(questions, isEmpty);
    await controller.send('Reserva?');
    expect(controller.messages.last.isError, isTrue);
    expect(controller.isLoading, isFalse);
    await controller.retry();
    expect(questions, ['Reserva?', 'Reserva?']);
    expect(controller.messages.where((message) => message.isUser).length, 1);
    expect(controller.messages.where((message) => message.isError), isEmpty);
    expect(controller.messages.last.text, 'Resposta oficial');
    await controller.retry();
    expect(questions.length, 2);
  });

  test('timeout aborta antes de retry e ignora resposta tardia', () async {
    final pending = Completer<http.Response>();
    var active = 0;
    var calls = 0;
    var aborted = false;
    final repository = ChatRepository(
      apiClient: ApiClient(
        generationTimeout: const Duration(milliseconds: 10),
        client: abortableClient(
          (request) async {
            expect(active, 0);
            active++;
            calls++;
            if (calls == 1) return pending.future;
            active--;
            return response();
          },
          onAbort: () {
            active--;
            aborted = true;
          },
        ),
      ),
    );
    final controller = ChatController(repository: repository);
    addTearDown(repository.close);
    addTearDown(controller.dispose);
    await controller.send('Reserva?');
    expect(aborted, isTrue);
    expect(active, 0);
    expect(controller.messages.last.isError, isTrue);
    await controller.retry();
    expect(calls, 2);
    expect(controller.messages.where((message) => message.isUser).length, 1);
    expect(controller.messages.last.isError, isFalse);
    final messages = controller.messages;
    pending.complete(response(answered: false));
    await Future<void>.delayed(Duration.zero);
    expect(controller.messages, messages);
    expect(controller.messages.last.isAbstained, isFalse);
  });

  test('nova pergunta substitui alvo de retry anterior', () async {
    final questions = <String>[];
    final controller = controllerFor((request) async {
      questions.add((jsonDecode(request.body) as Map)['message'] as String);
      return http.Response('', 500);
    });
    await controller.send('Primeira');
    await controller.send('Segunda');
    await controller.retry();
    expect(questions, ['Primeira', 'Segunda', 'Segunda']);
  });

  Map<String, dynamic> agentPayload() => <String, dynamic>{
    'query': 'Quanto gastei?',
    'status': 'abstained',
    'answer': 'Sem dados no recorte.',
    'model': null,
    'evidences': <dynamic>[],
    'calculations': <dynamic>[],
    'validation_issues': <dynamic>[],
    'steps': [
      {
        'agent': 'analysis',
        'status': 'abstained',
        'summary': 'Sem lançamentos no recorte.',
        'duration_ms': 1,
      },
    ],
    'total_ms': 1,
  };

  test('filtros de conta, dono e período viajam no modo multiagente', () async {
    var bodies = 0;
    final repository = ChatRepository(
      apiClient: ApiClient(
        client: abortableClient((request) async {
          bodies++;
          expect(request.url.path, '/v1/agents/ask');
          expect(jsonDecode(request.body), {
            'message': 'Quanto gastei?',
            'owner': 'empresa',
            'period': '2026-10',
          });
          return http.Response.bytes(
            utf8.encode(jsonEncode(agentPayload())),
            200,
          );
        }),
      ),
    );
    final controller = ChatController(repository: repository, multiAgent: true);
    addTearDown(repository.close);
    addTearDown(controller.dispose);
    controller.filters = const ChatFilters(owner: 'empresa', period: '2026-10');
    await controller.send('Quanto gastei?');
    expect(bodies, 1);
    expect(controller.messages.last.text, 'Sem dados no recorte.');
  });

  test('sem dados importados orienta a importação e não pergunta', () async {
    var requests = 0;
    final controller = controllerFor((_) async {
      requests++;
      return response();
    });
    controller.hasImportedData = () => false;
    await controller.send('Quanto gastei este mês?');
    expect(requests, 0);
    expect(controller.messages.length, 3);
    expect(controller.messages[1].isUser, isTrue);
    final guide = controller.messages.last;
    expect(guide.isUser, isFalse);
    expect(guide.isImportGuide, isTrue);
    expect(guide.isError, isFalse);
    expect(guide.text.toLowerCase(), contains('importe'));
    await controller.retry();
    expect(requests, 0);
  });

  test('volta a perguntar quando os dados chegam', () async {
    var imported = false;
    final controller = controllerFor((_) async => response());
    controller.hasImportedData = () => imported;
    await controller.send('Quanto gastei?');
    expect(controller.messages.last.isImportGuide, isTrue);
    imported = true;
    await controller.send('Quanto gastei de novo?');
    expect(controller.messages.last.text, 'Resposta oficial');
    expect(controller.messages.last.isImportGuide, isFalse);
  });

  test('sem dados, pergunta geral ainda vai ao RAG', () async {
    var requests = 0;
    final controller = controllerFor((_) async {
      requests++;
      return response();
    });
    controller.hasImportedData = () => false;
    await controller.send('Como montar uma reserva de emergência?');
    expect(requests, 1);
    expect(controller.messages.last.text, 'Resposta oficial');
    expect(controller.messages.last.isImportGuide, isFalse);
  });

  test('reconhece pergunta sobre os próprios dados', () {
    for (final q in [
      'Quanto gastei este mês?',
      'Qual o total da FATURA aberta?',
      'Quanto falta das parcelas?',
      'Quais são minhas dívidas?',
      'Qual o saldo da minha conta?',
    ]) {
      expect(asksAboutOwnData(q), isTrue, reason: q);
    }
    for (final q in [
      'Como montar uma reserva de emergência?',
      'Escreva um poema sobre futebol',
      'Como organizar o orçamento?',
      'Quanto devo guardar por mês?',
    ]) {
      expect(asksAboutOwnData(q), isFalse, reason: q);
    }
  });

  test('identifica mensagem de abstenção', () async {
    final controller = controllerFor((_) async => response(answered: false));
    await controller.send('Pergunta sem base');
    expect(controller.messages.last.isAbstained, isTrue);
    expect(controller.messages.last.isError, isFalse);
    expect(controller.messages.last.evidences, isEmpty);
  });

  for (final fails in [false, true]) {
    test(
      'dispose durante ${fails ? 'erro' : 'sucesso'} não notifica nem altera mensagens',
      () async {
        final pending = Completer<http.Response>();
        final controller = controllerFor((_) => pending.future);
        var notifications = 0;
        controller.addListener(() => notifications++);
        final sending = controller.send('Reserva?');
        expect(notifications, 1);
        await Future<void>.delayed(Duration.zero);
        final beforeDispose = controller.messages;
        controller.dispose();
        if (fails) {
          pending.completeError(http.ClientException('Sem conexão'));
        } else {
          pending.complete(response());
        }
        await sending;
        expect(notifications, 1);
        expect(controller.messages, beforeDispose);
        expect(controller.isLoading, isFalse);
        await controller.send('Depois do dispose');
        await controller.retry();
        expect(controller.messages, beforeDispose);
      },
    );
  }
}
