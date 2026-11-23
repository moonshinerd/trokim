import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart' as http_testing;
import 'package:trokim/core/network/api_client.dart';
import 'package:trokim/core/storage/library_sync.dart';
import 'package:trokim/core/storage/local_library_store.dart';

const _retrato =
    '{"version":1,"transactions":[{"uid":"a"}],"accounts":{"x":{"id":"x"}}}';

ApiClient _api(http.Client client) =>
    ApiClient(baseUrlProvider: () => 'http://api.test/v1', client: client);

void main() {
  group('armazenamento cifrado', () {
    late Directory dir;
    setUp(() => dir = Directory.systemTemp.createTempSync('trokim_'));
    tearDown(() => dir.deleteSync(recursive: true));

    test(
      'grava e lê de volta, e o arquivo não deixa o texto à mostra',
      () async {
        final keys = MemoryKeyStore();
        final store = EncryptedFileLibraryStore(
          File('${dir.path}/b.trokim'),
          keys,
        );
        await store.write(_retrato);
        expect(await store.read(), _retrato);
        final cru = File('${dir.path}/b.trokim')
            .readAsStringSync(encoding: latin1);
        expect(cru.contains('transactions'), isFalse);
      },
    );

    test('sem a chave certa a leitura falha', () async {
      final file = File('${dir.path}/b.trokim');
      await EncryptedFileLibraryStore(file, MemoryKeyStore()).write(_retrato);
      expect(
        () => EncryptedFileLibraryStore(file, MemoryKeyStore()).read(),
        throwsA(anything),
      );
    });

    test('um byte alterado é detectado', () async {
      final file = File('${dir.path}/b.trokim');
      final store = EncryptedFileLibraryStore(file, MemoryKeyStore());
      await store.write(_retrato);
      final bytes = file.readAsBytesSync();
      bytes[bytes.length ~/ 2] ^= 0xFF;
      file.writeAsBytesSync(bytes);
      expect(store.read(), throwsA(anything));
    });

    test('sem arquivo devolve nulo e limpar apaga', () async {
      final store = EncryptedFileLibraryStore(
        File('${dir.path}/b.trokim'),
        MemoryKeyStore(),
      );
      expect(await store.read(), isNull);
      await store.write(_retrato);
      await store.clear();
      expect(await store.read(), isNull);
    });
  });

  group('sincronização com a API', () {
    test('devolve à API o retrato guardado no aparelho', () async {
      String? recebido;
      final sync = LibrarySync(
        MemoryLibraryStore(_retrato),
        () => _api(
          http_testing.MockClient((request) async {
            expect(request.method, 'PUT');
            expect(request.url.path, '/v1/library/snapshot');
            recebido = request.body;
            return http.Response('{"added":{}}', 200);
          }),
        ),
      );
      expect(await sync.hydrate(), isTrue);
      expect(recebido, _retrato);
    });

    test('aparelho vazio traz os dados que a API já tinha', () async {
      final store = MemoryLibraryStore();
      final sync = LibrarySync(
        store,
        () => _api(
          http_testing.MockClient((_) async => http.Response(_retrato, 200)),
        ),
      );
      expect(await sync.hydrate(), isTrue);
      expect(await store.read(), _retrato);
    });

    test('API vazia não grava retrato vazio no aparelho', () async {
      final store = MemoryLibraryStore();
      final sync = LibrarySync(
        store,
        () => _api(
          http_testing.MockClient(
            (_) async => http.Response(
              '{"version":1,"transactions":[],"accounts":{}}',
              200,
            ),
          ),
        ),
      );
      await sync.hydrate();
      expect(await store.read(), isNull);
    });

    test('API fora do ar não apaga nem trava o aparelho', () async {
      final store = MemoryLibraryStore(_retrato);
      final sync = LibrarySync(
        store,
        () => _api(
          http_testing.MockClient(
            (_) async => throw const SocketException('x'),
          ),
        ),
      );
      expect(await sync.hydrate(), isFalse);
      expect(await sync.saveFromApi(), isFalse);
      expect(await store.read(), _retrato);
      expect(sync.lastError, isNotNull);
    });

    test('depois de uma alteração, grava o retrato atual da API', () async {
      final store = MemoryLibraryStore();
      final sync = LibrarySync(
        store,
        () => _api(
          http_testing.MockClient((request) async {
            expect(request.method, 'GET');
            return http.Response(_retrato, 200);
          }),
        ),
      );
      expect(await sync.saveFromApi(), isTrue);
      expect(await store.read(), _retrato);
    });

    test(
      'arquivo ilegível é posto de lado, avisa e não é sobrescrito',
      () async {
        final store = _IlegivelStore();
        final sync = LibrarySync(
          store,
          () => _api(
            http_testing.MockClient((_) async => http.Response(_retrato, 200)),
          ),
        );
        expect(await sync.hydrate(), isFalse);
        expect(sync.unreadable, isTrue);
        expect(store.wasQuarantined, isTrue);
        // Uma nova gravação válida limpa o aviso.
        expect(await sync.saveFromApi(), isTrue);
        expect(sync.unreadable, isFalse);
      },
    );

    test('arquivo corrompido em disco é preservado como .corrompido', () async {
      final dir = Directory.systemTemp.createTempSync('trokim_q_');
      addTearDown(() => dir.deleteSync(recursive: true));
      final file = File('${dir.path}/b.trokim');
      final store = EncryptedFileLibraryStore(file, MemoryKeyStore());
      await store.write(_retrato);
      final bytes = file.readAsBytesSync();
      bytes[bytes.length ~/ 2] ^= 0xFF;
      file.writeAsBytesSync(bytes);
      final sync = LibrarySync(
        store,
        () => _api(
          http_testing.MockClient((_) async => http.Response(_retrato, 200)),
        ),
      );
      expect(await sync.hydrate(), isFalse);
      expect(file.existsSync(), isFalse);
      expect(File('${file.path}.corrompido').readAsBytesSync(), bytes);
    });
  });
}

class _IlegivelStore extends MemoryLibraryStore {
  bool wasQuarantined = false;
  bool _broken = true;

  @override
  Future<String?> read() async {
    if (_broken) throw const FormatException('ilegível');
    return super.read();
  }

  @override
  Future<void> quarantine() async {
    wasQuarantined = true;
    _broken = false;
  }
}
