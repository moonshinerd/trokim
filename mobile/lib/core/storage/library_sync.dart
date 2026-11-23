import 'dart:async';

import 'package:flutter/foundation.dart';

import '../network/api_client.dart';
import 'local_library_store.dart';

/// Mantém o aparelho como fonte da verdade da biblioteca (ADR 0025).
///
/// Ao abrir o app, [hydrate] devolve à API o retrato guardado no aparelho (a API
/// só o mantém em memória). Depois de cada alteração, [saveFromApi] lê o retrato
/// atualizado da API e o grava cifrado no aparelho.
class LibrarySync {
  LibrarySync(this._store, this._newClient);

  final LocalLibraryStore _store;
  final ApiClient Function() _newClient;

  Future<void> _queue = Future<void>.value();

  /// Último erro de sincronização, para a interface avisar sem travar o uso.
  Object? lastError;

  /// A cópia guardada no aparelho existia, mas não pôde ser lida (foi posta de
  /// lado). A interface avisa e sugere restaurar um backup.
  bool unreadable = false;

  Future<T> _serial<T>(Future<T> Function() action) {
    final next = _queue.then((_) => action());
    _queue = next.then<void>((_) {}, onError: (_) {});
    return next;
  }

  /// Leva o retrato do aparelho para a API. Se o aparelho ainda não tem nada e a
  /// API já tem dados (versão antiga do app), traz os dados da API para o aparelho.
  /// Devolve `false` se a API não respondeu.
  Future<bool> hydrate() => _serial(() async {
    final client = _newClient();
    try {
      String? local;
      try {
        local = await _store.read();
      } on Object catch (error) {
        // Arquivo adulterado, truncado ou sem a chave: nunca devolve dado
        // errado e nunca o sobrescreve. Fica de lado e o usuário é avisado.
        unreadable = true;
        lastError = error;
        debugPrint(
          'Trokim: a cópia do aparelho não pôde ser lida (${error.runtimeType}).',
        );
        await _store.quarantine();
        return false;
      }
      if (local != null) {
        await client.putLibrarySnapshot(local);
      } else {
        final remote = await client.getLibrarySnapshot();
        if (!_isEmpty(remote)) await _store.write(remote);
      }
      lastError = null;
      return true;
    } on Object catch (error) {
      lastError = error;
      debugPrint(
        'Trokim: sincronização com o aparelho falhou (${error.runtimeType}).',
      );
      return false;
    } finally {
      client.close();
    }
  });

  /// Grava no aparelho o retrato atual da API. Falha em silêncio (guarda em
  /// [lastError]): a alteração já valeu na API e a próxima tentativa recupera.
  Future<bool> saveFromApi() => _serial(() async {
    final client = _newClient();
    try {
      await _store.write(await client.getLibrarySnapshot());
      lastError = null;
      unreadable = false;
      return true;
    } on Object catch (error) {
      lastError = error;
      debugPrint(
        'Trokim: sincronização com o aparelho falhou (${error.runtimeType}).',
      );
      return false;
    } finally {
      client.close();
    }
  });

  /// Apaga a cópia do aparelho (quando o usuário limpa os dados).
  Future<void> clearLocal() => _store.clear();

  static bool _isEmpty(String snapshot) =>
      !snapshot.contains('"transactions":[{') &&
      !snapshot.contains('"accounts":{"');
}
