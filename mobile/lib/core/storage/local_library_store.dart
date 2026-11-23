import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path_provider/path_provider.dart';

/// Onde o aparelho guarda a biblioteca do usuário (ADR 0025).
///
/// O conteúdo é o retrato da biblioteca em JSON. Quem usa a interface não sabe
/// se ele está num arquivo cifrado ou na memória (testes).
abstract class LocalLibraryStore {
  Future<String?> read();
  Future<void> write(String json);
  Future<void> clear();
}

/// Guarda o retrato só na memória: usado nos testes.
class MemoryLibraryStore implements LocalLibraryStore {
  MemoryLibraryStore([this._value]);
  String? _value;

  @override
  Future<String?> read() async => _value;

  @override
  Future<void> write(String json) async => _value = json;

  @override
  Future<void> clear() async => _value = null;
}

/// Chave de 256 bits do arquivo cifrado.
abstract class LibraryKeyStore {
  Future<List<int>> loadOrCreate();
}

class MemoryKeyStore implements LibraryKeyStore {
  MemoryKeyStore([List<int>? key]) : _key = key;
  List<int>? _key;

  @override
  Future<List<int>> loadOrCreate() async => _key ??= _randomBytes(32);
}

/// Guarda a chave no armazenamento seguro do sistema (Keystore no Android).
class SecureKeyStore implements LibraryKeyStore {
  SecureKeyStore([FlutterSecureStorage? storage])
    : _storage = storage ?? const FlutterSecureStorage();

  static const _name = 'trokim.library.key';
  final FlutterSecureStorage _storage;

  @override
  Future<List<int>> loadOrCreate() async {
    final saved = await _storage.read(key: _name);
    if (saved != null) {
      final key = base64Decode(saved);
      if (key.length == 32) return key;
    }
    final key = _randomBytes(32);
    await _storage.write(key: _name, value: base64Encode(key));
    return key;
  }
}

List<int> _randomBytes(int length) {
  final random = Random.secure();
  return List<int>.generate(length, (_) => random.nextInt(256));
}

/// Arquivo cifrado com AES-256-GCM. Sem a chave, o conteúdo é ilegível; um byte
/// alterado faz a leitura falhar em vez de devolver dado errado.
class EncryptedFileLibraryStore implements LocalLibraryStore {
  EncryptedFileLibraryStore(this._file, this._keys);

  static const _magic = [0x54, 0x4B, 0x4D, 0x31]; // "TKM1"
  static const _nonceSize = 12;
  static const _macSize = 16;

  final File _file;
  final LibraryKeyStore _keys;
  final AesGcm _cipher = AesGcm.with256bits();

  /// O arquivo fica na pasta privada do app, que o Android isola dos demais.
  static Future<EncryptedFileLibraryStore> open([LibraryKeyStore? keys]) async {
    final dir = await getApplicationSupportDirectory();
    return EncryptedFileLibraryStore(
      File('${dir.path}/biblioteca.trokim'),
      keys ?? SecureKeyStore(),
    );
  }

  @override
  Future<String?> read() async {
    if (!await _file.exists()) return null;
    final bytes = await _file.readAsBytes();
    const header = 4 + _nonceSize;
    if (bytes.length < header + _macSize ||
        !_startsWithMagic(bytes)) {
      throw const FormatException('Arquivo da biblioteca inválido.');
    }
    final nonce = bytes.sublist(4, header);
    final cipherText = bytes.sublist(header, bytes.length - _macSize);
    final mac = Mac(bytes.sublist(bytes.length - _macSize));
    final key = SecretKey(await _keys.loadOrCreate());
    final plain = await _cipher.decrypt(
      SecretBox(cipherText, nonce: nonce, mac: mac),
      secretKey: key,
      aad: _magic,
    );
    return utf8.decode(plain);
  }

  @override
  Future<void> write(String json) async {
    final key = SecretKey(await _keys.loadOrCreate());
    final box = await _cipher.encrypt(
      utf8.encode(json),
      secretKey: key,
      aad: _magic,
    );
    final out = BytesBuilder()
      ..add(_magic)
      ..add(box.nonce)
      ..add(box.cipherText)
      ..add(box.mac.bytes);
    // Grava num arquivo temporário e troca: uma queda no meio não corrompe o anterior.
    final temp = File('${_file.path}.tmp');
    await temp.parent.create(recursive: true);
    await temp.writeAsBytes(out.takeBytes(), flush: true);
    await temp.rename(_file.path);
  }

  @override
  Future<void> clear() async {
    if (await _file.exists()) await _file.delete();
  }

  bool _startsWithMagic(List<int> bytes) {
    for (var i = 0; i < _magic.length; i++) {
      if (bytes[i] != _magic[i]) return false;
    }
    return true;
  }
}
