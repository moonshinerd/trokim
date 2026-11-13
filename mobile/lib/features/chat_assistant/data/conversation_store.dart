import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../domain/conversation.dart';

/// Onde as conversas ficam guardadas (sempre no aparelho).
abstract class ConversationStore {
  Future<List<Conversation>> load();
  Future<void> save(List<Conversation> conversations);
}

/// Guarda tudo em um JSON nas preferências do app. Simples e suficiente para
/// centenas de conversas; trocar por SQLite exige só outra implementação.
class PrefsConversationStore implements ConversationStore {
  static const _key = 'conversations_v1';

  @override
  Future<List<Conversation>> load() async {
    final raw = (await SharedPreferences.getInstance()).getString(_key);
    if (raw == null || raw.isEmpty) return [];
    try {
      return (jsonDecode(raw) as List<dynamic>)
          .map((c) => Conversation.fromJson(c as Map<String, dynamic>))
          .toList();
    } on Object {
      // Dado corrompido não pode impedir o app de abrir.
      return [];
    }
  }

  @override
  Future<void> save(List<Conversation> conversations) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      _key,
      jsonEncode(conversations.map((c) => c.toJson()).toList()),
    );
  }
}

/// Sem persistência (testes).
class MemoryConversationStore implements ConversationStore {
  List<Conversation> saved = [];

  @override
  Future<List<Conversation>> load() async => List.of(saved);

  @override
  Future<void> save(List<Conversation> conversations) async {
    saved = List.of(conversations);
  }
}
