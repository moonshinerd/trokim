import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:trokim/core/network/api_client.dart';
import 'package:trokim/features/chat_assistant/data/chat_repository.dart';
import 'package:trokim/features/chat_assistant/domain/chat_models.dart';

import 'support/abortable_client.dart';

void main() {
  ChatRepository repositoryFor(
    Future<http.Response> Function(http.Request) handler, {
    Duration timeout = const Duration(seconds: 15),
  }) {
    final repository = ChatRepository(
      apiClient: ApiClient(
        baseUrl: 'http://localhost:8000/v1',
        client: abortableClient(handler),
        generationTimeout: timeout,
      ),
    );
    addTearDown(repository.close);
    return repository;
  }

  Map<String, dynamic> payload({bool answered = true}) => <String, dynamic>{
    'query': 'Como criar uma reserva?',
    'mode': 'grounded',
    'model': 'qwen2.5',
    'answered': answered,
    'status': answered ? 'grounded' : 'abstained',
    'answer': answered ? 'Organize sua reserva.' : 'Não há evidências suficientes.',
    'evidences': answered
        ? [
            <String, dynamic>{
              'id': 'cvm_1',
              'document_id': 'cvm.txt',
              'source_name': 'CVM',
              'source_url': 'https://www.gov.br/investidor/',
              'document_title': 'Reserva de emergência',
              'section': 'Planejamento',
              'content': 'Mantenha uma reserva.',
              'score': 1,
            },
          ]
        : [],
  };

  test('envia contrato HTTP e converte resposta fundamentada', () async {
    final repository = repositoryFor((request) async {
      expect(request.method, 'POST');
      expect(request.url.toString(), 'http://localhost:8000/v1/chat/generate');
      expect(request.headers['content-type'], 'application/json');
      expect(jsonDecode(request.body), {
        'message': 'Como criar uma reserva?',
        'mode': 'grounded',
      });
      return http.Response.bytes(utf8.encode(jsonEncode(payload())), 200);
    });
    final reply = await repository.ask('Como criar uma reserva?');
    expect(reply.answered, isTrue);
    expect(reply.status, AssistantStatus.grounded);
    expect(reply.query, 'Como criar uma reserva?');
    expect(reply.mode, 'grounded');
    expect(reply.model, 'qwen2.5');
    expect(reply.answer, 'Organize sua reserva.');
    final evidence = reply.evidences.single;
    expect(evidence.id, 'cvm_1');
    expect(evidence.documentId, 'cvm.txt');
    expect(evidence.sourceName, 'CVM');
    expect(evidence.sourceUrl, 'https://www.gov.br/investidor/');
    expect(evidence.documentTitle, 'Reserva de emergência');
    expect(evidence.section, 'Planejamento');
    expect(evidence.content, 'Mantenha uma reserva.');
    expect(evidence.score, 1.0);
    expect(() => reply.evidences.clear(), throwsUnsupportedError);
  });

  for (final omitFields in [true, false]) {
    test('aceita metadados opcionais ${omitFields ? 'ausentes' : 'nulos'}', () async {
      final body = payload();
      final evidence = (body['evidences'] as List).single as Map;
      for (final key in ['document_id', 'source_url']) {
        if (omitFields) {
          evidence.remove(key);
        } else {
          evidence[key] = null;
        }
      }
      final repository = repositoryFor(
        (_) async => http.Response.bytes(utf8.encode(jsonEncode(body)), 200),
      );
      final reply = await repository.ask('Reserva?');
      expect(reply.evidences.single.documentId, isNull);
      expect(reply.evidences.single.sourceUrl, isNull);
    });
  }

  test('converte abstenção sem evidências', () async {
    final repository = repositoryFor(
      (_) async => http.Response.bytes(utf8.encode(jsonEncode(payload(answered: false))), 200),
    );
    final reply = await repository.ask('Pergunta sem base');
    expect(reply.answered, isFalse);
    expect(reply.status, AssistantStatus.abstained);
    expect(reply.evidences, isEmpty);
  });

  for (final status in [500, 502, 503, 504, 422]) {
    test('traduz HTTP $status para mensagem amigável', () async {
      final repository = repositoryFor(
        (_) async => http.Response('Erro interno sensível', status),
      );
      await expectLater(
        repository.ask('Reserva?'),
        throwsA(isA<ChatException>().having(
          (error) => error.message,
          'mensagem',
          contains(status == 422 ? '1000 caracteres' : 'indisponível'),
        )),
      );
    });
  }

  for (final error in [
    const SocketException('Detalhe de rede'),
    http.ClientException('Detalhe de rede'),
  ]) {
    test('traduz ${error.runtimeType} como backend offline', () async {
      final repository = repositoryFor((_) async => throw error);
      await expectLater(
        repository.ask('Reserva?'),
        throwsA(isA<ChatException>().having(
          (error) => error.message,
          'mensagem',
          contains('Verifique sua conexão'),
        )),
      );
    });
  }

  test('traduz timeout com duração curta injetada', () async {
    final pending = Completer<http.Response>();
    final repository = repositoryFor(
      (_) => pending.future,
      timeout: const Duration(milliseconds: 1),
    );
    await expectLater(
      repository.ask('Reserva?'),
      throwsA(isA<ChatException>().having(
        (error) => error.message,
        'mensagem',
        contains('demorou'),
      )),
    );
    pending.complete(http.Response('{}', 200));
  });

  for (final body in ['não é JSON', '[]', '{}']) {
    test('traduz resposta inválida: $body', () async {
      final repository = repositoryFor((_) async => http.Response.bytes(utf8.encode(body), 200));
      await expectLater(
        repository.ask('Reserva?'),
        throwsA(isA<ChatException>().having(
          (error) => error.message,
          'mensagem',
          contains('resposta inválida'),
        )),
      );
    });
  }

  final incompatiblePayloads = <String, Map<String, dynamic>>{
    'modo experimental': {'mode': 'pure', 'status': 'pure_baseline'},
    'status experimental': {'status': 'naive_rag'},
    'status desconhecido': {'status': 'unknown'},
    'resposta vazia': {'answer': '   '},
    'modelo ausente': {'model': null},
    'consulta ausente': {'query': null},
    'contrato extrativo': {'mode': null, 'model': null},
    'fundamentação sem fontes': {'evidences': []},
    'status e answered divergentes': {'answered': false},
    'abstenção com fontes': {'status': 'abstained', 'answered': false},
    'evidências inválidas': {'evidences': 'inválido'},
  };
  for (final entry in incompatiblePayloads.entries) {
    test('rejeita ${entry.key} sem fallback', () async {
      var requests = 0;
      final repository = repositoryFor((request) async {
        requests++;
        expect(request.url.path, '/v1/chat/generate');
        return http.Response.bytes(
          utf8.encode(jsonEncode({...payload(), ...entry.value})),
          200,
        );
      });
      await expectLater(
        repository.ask('Reserva?'),
        throwsA(isA<ChatException>().having(
          (error) => error.message,
          'mensagem',
          contains('resposta inválida'),
        )),
      );
      expect(requests, 1);
    });
  }

  test('abstenção não pode informar answered verdadeiro', () async {
    final body = payload(answered: false)..['answered'] = true;
    final repository = repositoryFor(
      (_) async => http.Response.bytes(utf8.encode(jsonEncode(body)), 200),
    );
    await expectLater(repository.ask('Reserva?'), throwsA(isA<ChatException>()));
  });

  test('timeout da geração é independente do prazo das demais chamadas', () async {
    final pending = Completer<http.Response>();
    final client = ApiClient(
      client: MockClient((_) => pending.future),
      timeout: const Duration(milliseconds: 1),
      generationTimeout: const Duration(seconds: 1),
    );
    final repository = ChatRepository(apiClient: client);
    addTearDown(repository.close);
    final asking = repository.ask('Reserva?');
    await Future<void>.delayed(const Duration(milliseconds: 10));
    pending.complete(http.Response.bytes(utf8.encode(jsonEncode(payload())), 200));
    expect((await asking).status, AssistantStatus.grounded);
  });

  test('falha do modelo é erro e não abstenção nem resposta extrativa', () async {
    var requests = 0;
    final repository = repositoryFor((request) async {
      requests++;
      expect(request.url.path, '/v1/chat/generate');
      return http.Response('Erro interno sensível do modelo', 500);
    });
    await expectLater(
      repository.ask('Reserva?'),
      throwsA(isA<ChatException>().having(
        (error) => error.message,
        'mensagem',
        allOf(contains('indisponível'), isNot(contains('sensível'))),
      )),
    );
    expect(requests, 1);
  });

  test('timeout também aborta durante a leitura do corpo', () async {
    var aborted = false;
    final transport = MockClient.streaming((request, body) async {
      await body.toBytes();
      final responseBody = StreamController<List<int>>();
      final abort = (request as http.Abortable).abortTrigger!;
      unawaited(abort.then((_) async {
        aborted = true;
        responseBody.addError(http.RequestAbortedException(request.url));
        await responseBody.close();
      }));
      return http.StreamedResponse(responseBody.stream, 200);
    });
    final repository = ChatRepository(apiClient: ApiClient(
      client: transport,
      generationTimeout: const Duration(milliseconds: 10),
    ));
    addTearDown(repository.close);
    await expectLater(repository.ask('Reserva?'), throwsA(
      isA<ChatException>().having(
        (error) => error.message, 'mensagem', contains('demorou'),
      ),
    ));
    expect(aborted, isTrue);
  });

  test('fechar cliente aborta uma geração pendente', () async {
    final started = Completer<void>();
    var aborted = false;
    final client = ApiClient(client: abortableClient((_) {
      started.complete();
      return Completer<http.Response>().future;
    }, onAbort: () => aborted = true));
    addTearDown(client.close);
    final asking = client.generateAssistant('Reserva?');
    final assertion = expectLater(asking, throwsA(isA<http.RequestAbortedException>()));
    await started.future;
    client.close();
    await assertion;
    expect(aborted, isTrue);
  });

  for (final duration in [Duration.zero, const Duration(seconds: -1)]) {
    test('rejeita prazo não positivo: $duration', () {
      expect(() => ApiClient(generationTimeout: duration), throwsArgumentError);
    });
  }

  test('ApiClient expõe status HTTP sem decodificar corpo de erro', () async {
    final client = ApiClient(client: MockClient((_) async => http.Response('', 500)));
    addTearDown(client.close);
    await expectLater(
      client.generateAssistant('Reserva?'),
      throwsA(isA<ApiException>().having((error) => error.statusCode, 'status', 500)),
    );
  });
}
