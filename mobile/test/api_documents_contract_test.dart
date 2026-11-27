import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:trokim/core/network/api_client.dart';

void main() {
  ApiClient cliente(Future<http.Response> Function(http.Request) responder) {
    final api = ApiClient(
      baseUrl: 'http://localhost:8000/v1',
      client: MockClient(responder),
    );
    addTearDown(api.close);
    return api;
  }

  test('consulta motores no endereço configurado sem duplicar v1', () async {
    final api = cliente((pedido) async {
      expect(pedido.method, 'GET');
      expect(pedido.url.path, '/v1/documents/engines');
      return http.Response('{"ocr":"rapidocr","vision":null}', 200);
    });
    expect(await api.getDocumentEngines(), {'ocr': 'rapidocr', 'vision': null});
  });

  test('extração padrão envia arquivo e OCR sem autorizar remoto', () async {
    final api = cliente((pedido) async {
      expect(pedido.method, 'POST');
      expect(pedido.url.path, '/v1/documents/extract');
      expect(
        pedido.headers['content-type'],
        startsWith('multipart/form-data;'),
      );
      expect(pedido.body, contains('name="file"; filename="sintetico.png"'));
      expect(pedido.body, contains('name="engine"\r\n\r\nocr'));
      expect(pedido.body, contains('name="allow_remote"\r\n\r\nfalse'));
      expect(pedido.body, isNot(contains('name="account_id"')));
      return http.Response('{}', 200);
    });
    await api.extractDocument('sintetico.png', [1, 2, 3]);
  });

  test(
    'extração envia conta e autorização explícita quando solicitadas',
    () async {
      final api = cliente((pedido) async {
        expect(pedido.body, contains('name="engine"\r\n\r\nvision'));
        expect(pedido.body, contains('name="allow_remote"\r\n\r\ntrue'));
        expect(
          pedido.body,
          contains('name="account_id"\r\n\r\nconta-sintetica'),
        );
        return http.Response('{}', 200);
      });
      await api.extractDocument(
        'sintetico.png',
        [1, 2, 3],
        engine: 'vision',
        allowRemote: true,
        accountId: 'conta-sintetica',
      );
    },
  );

  test('confirma somente o contrato revisado, incluindo origem', () async {
    final revisado = <String, Object?>{
      'origin': 'documento',
      'kind': 'pix_receipt',
      'amount': '308.76',
      'date': '2026-11-27',
      'description': 'Compra sintética revisada',
      'transactions': <Object?>[],
    };
    final api = cliente((pedido) async {
      expect(pedido.method, 'POST');
      expect(pedido.url.path, '/v1/documents/confirm');
      expect(jsonDecode(pedido.body), revisado);
      return http.Response('{"uid":"documento-sintetico"}', 200);
    });
    expect((await api.confirmDocument(revisado))['uid'], 'documento-sintetico');
  });

  for (final status in [403, 413, 415, 422, 503]) {
    test('preserva mensagem estruturada do erro HTTP $status', () async {
      final mensagem = 'Falha sintética $status: confira o documento.';
      final api = cliente(
        (_) async => http.Response.bytes(
          utf8.encode(
            jsonEncode({
              'detail': {'code': 'ERRO_SINTETICO', 'message': mensagem},
            }),
          ),
          status,
        ),
      );
      await expectLater(
        api.extractDocument('sintetico.png', [1]),
        throwsA(
          isA<ApiException>()
              .having((erro) => erro.statusCode, 'statusCode', status)
              .having((erro) => erro.detail, 'detail', mensagem),
        ),
      );
    });
  }

  test(
    'mantém compatibilidade com detalhe textual de outros endpoints',
    () async {
      final api = cliente(
        (_) async => http.Response('{"detail":"Servidor indisponivel"}', 503),
      );
      await expectLater(
        api.getDocumentEngines(),
        throwsA(
          isA<ApiException>().having(
            (erro) => erro.detail,
            'detail',
            'Servidor indisponivel',
          ),
        ),
      );
    },
  );
}
