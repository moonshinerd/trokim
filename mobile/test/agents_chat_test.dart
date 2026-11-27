import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:trokim/core/network/api_client.dart';
import 'package:trokim/features/chat_assistant/data/chat_repository.dart';

import 'support/abortable_client.dart';

void main() {
  test(
    'envia pergunta ao endpoint multiagente e converte a resposta',
    () async {
      final payload = {
        'query': 'Como organizar?',
        'status': 'abstained',
        'answer': 'Não encontrei base suficiente.',
        'model': null,
        'evidences': <dynamic>[],
        'calculations': <dynamic>[],
        'validation_issues': <dynamic>[],
        'steps': [
          {
            'agent': 'research',
            'status': 'abstained',
            'summary': 'Não há fontes suficientes.',
            'duration_ms': 1,
          },
        ],
        'total_ms': 1,
      };
      final client = ApiClient(
        baseUrl: 'http://localhost:8000/v1',
        client: abortableClient((request) async {
          expect(request.url.path, '/v1/agents/ask');
          expect(jsonDecode(request.body), {'message': 'Como organizar?'});
          return http.Response.bytes(utf8.encode(jsonEncode(payload)), 200);
        }),
      );
      final repository = ChatRepository(apiClient: client);
      addTearDown(repository.close);
      final result = await repository.askAgents('Como organizar?');
      expect(result.answer, 'Não encontrei base suficiente.');
      expect(result.steps.single.agent.name, 'research');
    },
  );

  test('envia filtros de conta, dono e período no corpo da pergunta', () async {
    final payload = {
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
    final client = ApiClient(
      baseUrl: 'http://localhost:8000/v1',
      client: abortableClient((request) async {
        expect(request.url.path, '/v1/agents/ask');
        expect(jsonDecode(request.body), {
          'message': 'Quanto gastei?',
          'account_id': 'nubank:cartao-pf',
          'owner': 'pessoal',
          'period': 'fatura aberta',
        });
        return http.Response.bytes(utf8.encode(jsonEncode(payload)), 200);
      }),
    );
    final repository = ChatRepository(apiClient: client);
    addTearDown(repository.close);
    final result = await repository.askAgents(
      'Quanto gastei?',
      accountId: 'nubank:cartao-pf',
      owner: 'pessoal',
      period: 'fatura aberta',
    );
    expect(result.answer, 'Sem dados no recorte.');
  });

  test('omite filtros ausentes do corpo da pergunta', () async {
    final payload = {
      'query': 'Quanto gastei?',
      'status': 'abstained',
      'answer': 'Sem dados.',
      'model': null,
      'evidences': <dynamic>[],
      'calculations': <dynamic>[],
      'validation_issues': <dynamic>[],
      'steps': [
        {
          'agent': 'analysis',
          'status': 'abstained',
          'summary': 'Sem lançamentos.',
          'duration_ms': 1,
        },
      ],
      'total_ms': 1,
    };
    final client = ApiClient(
      baseUrl: 'http://localhost:8000/v1',
      client: abortableClient((request) async {
        expect(jsonDecode(request.body), {'message': 'Quanto gastei?'});
        return http.Response.bytes(utf8.encode(jsonEncode(payload)), 200);
      }),
    );
    final repository = ChatRepository(apiClient: client);
    addTearDown(repository.close);
    await repository.askAgents('Quanto gastei?');
  });

  test('transforma payload multiagente inválido em erro amigável', () async {
    final repository = ChatRepository(
      apiClient: ApiClient(
        baseUrl: 'http://localhost:8000/v1',
        client: abortableClient((_) async => http.Response('{}', 200)),
      ),
    );
    addTearDown(repository.close);
    await expectLater(
      repository.askAgents('Pergunta'),
      throwsA(isA<ChatException>()),
    );
  });

  test('transforma falha de rede em mensagem amigável', () async {
    final repository = ChatRepository(
      apiClient: ApiClient(
        baseUrl: 'http://localhost:8000/v1',
        client: abortableClient(
          (_) async => throw const SocketException('offline'),
        ),
      ),
    );
    addTearDown(repository.close);
    await expectLater(
      repository.askAgents('Pergunta'),
      throwsA(isA<ChatException>()),
    );
  });
}
