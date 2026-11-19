import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import '../../features/transactions/presentation/transactions_screen.dart';

/// Recebe arquivos enviados ao Trokim por "Compartilhar" ou "Abrir com" (Android).
///
/// O lado nativo (`MainActivity.kt`) lê o arquivo e entrega nome e bytes por um canal. O arquivo
/// que abriu o app fica guardado até [takeInitialFile]; os que chegam com o app aberto saem em
/// [files]. Em plataformas sem o canal (web, testes, iOS), não há arquivos e nada falha.
class SharedFileReceiver {
  SharedFileReceiver({MethodChannel? channel})
    : _channel = channel ?? const MethodChannel(channelName) {
    _channel.setMethodCallHandler(_handle);
  }

  static const channelName = 'br.com.trokim/shared_file';

  final MethodChannel _channel;
  final _files = StreamController<PickedStatement>.broadcast();

  /// Arquivos compartilhados com o app já aberto.
  Stream<PickedStatement> get files => _files.stream;

  Future<Object?> _handle(MethodCall call) async {
    if (call.method == 'fileShared') {
      final file = parse(call.arguments);
      if (file != null) _files.add(file);
    }
    return null;
  }

  /// Arquivo que abriu o app, se houver (entregue uma vez só).
  Future<PickedStatement?> takeInitialFile() async {
    try {
      return parse(await _channel.invokeMethod<Object?>('takeInitialFile'));
    } on MissingPluginException {
      return null;
    } on PlatformException {
      return null;
    }
  }

  /// Converte o mapa do canal (`name`, `bytes`) no arquivo do fluxo de importação.
  @visibleForTesting
  static PickedStatement? parse(Object? raw) {
    if (raw is! Map) return null;
    final name = raw['name'];
    final bytes = raw['bytes'];
    if (name is! String || name.isEmpty || bytes is! Uint8List) return null;
    if (bytes.isEmpty) return null;
    final copy = List<int>.unmodifiable(bytes);
    return PickedStatement(name, () async => copy);
  }

  void dispose() {
    _channel.setMethodCallHandler(null);
    _files.close();
  }
}
