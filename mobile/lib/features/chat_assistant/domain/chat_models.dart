enum AssistantStatus {
  grounded,
  abstained;

  static AssistantStatus fromJson(Object? value) => switch (value) {
        'grounded' => AssistantStatus.grounded,
        'abstained' => AssistantStatus.abstained,
        _ => throw const FormatException('Status incompatível com o chat.'),
      };
}

String _requiredText(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! String || value.trim().isEmpty) {
    throw FormatException('Campo obrigatório inválido: $key.');
  }
  return value;
}

final class Evidence {
  final String id;
  final String? documentId;
  final String sourceName;
  final String? sourceUrl;
  final String documentTitle;
  final String section;
  final String content;
  final double score;

  const Evidence._({
    required this.id,
    this.documentId,
    required this.sourceName,
    this.sourceUrl,
    required this.documentTitle,
    required this.section,
    required this.content,
    required this.score,
  });

  factory Evidence.fromJson(Map<String, dynamic> json) {
    final score = json['score'];
    if (score is! num || !score.isFinite) {
      throw const FormatException('Relevância inválida na evidência.');
    }
    return Evidence._(
      id: _requiredText(json, 'id'),
      documentId: json['document_id'] as String?,
      sourceName: _requiredText(json, 'source_name'),
      sourceUrl: json['source_url'] as String?,
      documentTitle: _requiredText(json, 'document_title'),
      section: _requiredText(json, 'section'),
      content: _requiredText(json, 'content'),
      score: score.toDouble(),
    );
  }
}

final class AssistantReply {
  final String query;
  final String model;
  final AssistantStatus status;
  final String answer;
  final List<Evidence> evidences;

  bool get isAbstained => status == AssistantStatus.abstained;
  bool get answered => !isAbstained;
  String get mode => 'grounded';

  AssistantReply._({
    required this.query,
    required this.model,
    required this.status,
    required this.answer,
    required List<Evidence> evidences,
  }) : evidences = List.unmodifiable(evidences);

  factory AssistantReply.fromJson(Map<String, dynamic> json) {
    if (json['mode'] != 'grounded') {
      throw const FormatException('Modo incompatível com o chat.');
    }
    final status = AssistantStatus.fromJson(json['status']);
    final answered = status == AssistantStatus.grounded;
    if (json['answered'] != answered) {
      throw const FormatException('Status e resposta divergentes.');
    }
    final evidences = (json['evidences'] as List<dynamic>)
        .map((value) => Evidence.fromJson(value as Map<String, dynamic>))
        .toList();
    if (answered && evidences.isEmpty) {
      throw const FormatException('Resposta fundamentada sem evidências.');
    }
    if (!answered && evidences.isNotEmpty) {
      throw const FormatException('Abstenção com evidências.');
    }
    return AssistantReply._(
      query: _requiredText(json, 'query'),
      model: _requiredText(json, 'model'),
      status: status,
      answer: _requiredText(json, 'answer'),
      evidences: evidences,
    );
  }
}

class ChatMessage {
  final bool isUser;
  final String text;
  final List<Evidence> evidences;
  final bool isError;
  final AssistantStatus? status;

  bool get isAbstained => status == AssistantStatus.abstained;

  ChatMessage({
    required this.isUser,
    required this.text,
    List<Evidence> evidences = const [],
    this.isError = false,
    this.status,
  }) : evidences = List.unmodifiable(evidences);
}
