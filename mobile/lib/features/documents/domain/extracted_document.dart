enum DocumentKind { pixReceipt, boleto, cardInvoice, bankStatement, other }

enum DocumentQuality { legible, partial, illegible }

enum FieldSource { textLayer, ocr, vlm }

class ExtractedField {
  const ExtractedField({
    required this.key,
    required this.value,
    required this.confidence,
    required this.source,
  });
  final String key;
  final Object? value;
  final double confidence;
  final FieldSource source;
}

class ExtractedTransaction {
  const ExtractedTransaction({
    this.date,
    required this.description,
    this.amount,
    this.installment,
    required this.confidence,
  });
  final DateTime? date;
  final String description;
  final double? amount;
  final String? installment;
  final double confidence;
}

class QualityReport {
  const QualityReport({
    required this.quality,
    required this.sharpness,
    required this.resolution,
    this.meanOcrConfidence,
    this.reasons = const [],
  });
  final DocumentQuality quality;
  final double sharpness;
  final (int, int) resolution;
  final double? meanOcrConfidence;
  final List<String> reasons;
}

class ValidationIssue {
  const ValidationIssue({
    required this.code,
    required this.message,
    required this.blocking,
    this.fieldKey,
  });
  final String code;
  final String message;
  final bool blocking;
  final String? fieldKey;
}

/// Espelha o contrato publicado no épico #86; `needsReview` é sempre true.
class ExtractedDocument {
  const ExtractedDocument({
    required this.kind,
    required this.quality,
    required this.fields,
    this.bank,
    this.transactions = const [],
    this.issues = const [],
    this.needsReview = true,
    this.abstained = false,
    this.reason,
    required this.engine,
  });

  final DocumentKind kind;
  final String? bank;
  final QualityReport quality;
  final List<ExtractedField> fields;
  final List<ExtractedTransaction> transactions;
  final List<ValidationIssue> issues;
  final bool needsReview;
  final bool abstained;
  final String? reason;
  final String engine;

  bool get canConfirm =>
      !abstained &&
      quality.quality != DocumentQuality.illegible &&
      needsReview &&
      !issues.any((issue) => issue.blocking);

  bool canConfirmAfter(Map<String, String> edits) {
    if (abstained ||
        quality.quality == DocumentQuality.illegible ||
        !needsReview) {
      return false;
    }
    return issues.where((issue) => issue.blocking).every((issue) {
      final key = issue.fieldKey;
      if (key == null) return false;
      final fieldIndex = fields.indexWhere((field) => field.key == key);
      final original = fieldIndex < 0
          ? null
          : fields[fieldIndex].value?.toString() ?? '';
      final value = edits[key] ?? original;
      return value != null && value.trim().isNotEmpty;
    });
  }
}

/// Resultado aprovado pela pessoa; o app não persiste nada nesta fase.
class ReviewedDocument {
  const ReviewedDocument({required this.fields, required this.transactions});
  final List<ExtractedField> fields;
  final List<ExtractedTransaction> transactions;
}
