import 'chat_models.dart';

/// Situação do título de uma conversa.
enum TitleState {
  /// Título provisório (a primeira pergunta) enquanto o LLM não nomeou.
  placeholder,

  /// O LLM está nomeando agora.
  generating,

  /// Nomeada pelo LLM.
  auto,

  /// Renomeada pelo usuário (nunca é sobrescrita).
  manual,
}

/// Uma conversa do assistente, guardada só no aparelho.
class Conversation {
  Conversation({
    required this.id,
    required this.title,
    required this.titleState,
    required this.createdAt,
    required this.updatedAt,
    required List<ChatMessage> messages,
    this.titleAttempts = 0,
  }) : messages = List.unmodifiable(messages);

  final String id;
  final String title;
  final TitleState titleState;
  final DateTime createdAt;
  final DateTime updatedAt;
  final List<ChatMessage> messages;

  /// Quantas vezes já tentamos nomear com o LLM (limita as tentativas).
  final int titleAttempts;

  /// Última pergunta do usuário, para a prévia na lista.
  String get preview {
    for (final m in messages.reversed) {
      if (m.isUser) return m.text;
    }
    return '';
  }

  Conversation copyWith({
    String? title,
    TitleState? titleState,
    DateTime? updatedAt,
    List<ChatMessage>? messages,
    int? titleAttempts,
  }) =>
      Conversation(
        id: id,
        title: title ?? this.title,
        titleState: titleState ?? this.titleState,
        createdAt: createdAt,
        updatedAt: updatedAt ?? this.updatedAt,
        messages: messages ?? this.messages,
        titleAttempts: titleAttempts ?? this.titleAttempts,
      );

  factory Conversation.fromJson(Map<String, dynamic> json) {
    final state = TitleState.values.firstWhere(
      (s) => s.name == json['title_state'],
      orElse: () => TitleState.placeholder,
    );
    return Conversation(
      id: json['id'] as String,
      title: json['title'] as String,
      // "gerando" é transitório: ao reabrir o app volta a ser provisório.
      titleState:
          state == TitleState.generating ? TitleState.placeholder : state,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
      messages: (json['messages'] as List<dynamic>)
          .map((m) => ChatMessage.fromJson(m as Map<String, dynamic>))
          .toList(),
      titleAttempts: json['title_attempts'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'title': title,
        'title_state': titleState.name,
        'created_at': createdAt.toIso8601String(),
        'updated_at': updatedAt.toIso8601String(),
        'messages': messages.map((m) => m.toJson()).toList(),
        'title_attempts': titleAttempts,
      };
}
