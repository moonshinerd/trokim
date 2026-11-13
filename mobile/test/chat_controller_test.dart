import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:trokim/core/network/api_client.dart';
import 'package:trokim/features/chat_assistant/data/chat_repository.dart';
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
