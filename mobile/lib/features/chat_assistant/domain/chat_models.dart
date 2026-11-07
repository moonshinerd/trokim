class Evidence {
  final String id;
  final String? documentId;
  final String sourceName;
  final String? sourceUrl;
  final String documentTitle;
  final String section;
  final String content;
  final double score;

  const Evidence({
    required this.id,
    this.documentId,
    required this.sourceName,
    this.sourceUrl,
    required this.documentTitle,
    required this.section,
    required this.content,
    required this.score,
  });

  factory Evidence.fromJson(Map<String, dynamic> json) => Evidence(
        id: json['id'] as String,
        documentId: json['document_id'] as String?,
        sourceName: json['source_name'] as String,
        sourceUrl: json['source_url'] as String?,
        documentTitle: json['document_title'] as String,
        section: json['section'] as String,
        content: json['content'] as String,
        score: (json['score'] as num).toDouble(),
      );
}

class AssistantReply {
  final bool answered;
  final String status;
  final String answer;
  final List<Evidence> evidences;

  AssistantReply({
    required this.answered,
    required this.status,
    required this.answer,
    required List<Evidence> evidences,
  }) : evidences = List.unmodifiable(evidences);

  factory AssistantReply.fromJson(Map<String, dynamic> json) => AssistantReply(
        answered: json['answered'] as bool,
        status: json['status'] as String,
        answer: json['answer'] as String,
        evidences: (json['evidences'] as List<dynamic>)
            .map((value) => Evidence.fromJson(value as Map<String, dynamic>))
            .toList(),
      );
}

class ChatMessage {
  final bool isUser;
  final String text;
  final List<Evidence> evidences;
  final bool isError;
  final bool isAbstained;

  ChatMessage({
    required this.isUser,
    required this.text,
    List<Evidence> evidences = const [],
    this.isError = false,
    this.isAbstained = false,
  }) : evidences = List.unmodifiable(evidences);
}
