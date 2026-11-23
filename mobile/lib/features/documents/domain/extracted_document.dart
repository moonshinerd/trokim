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

  bool get canConfirm => canConfirmAfter(const {});

  /// A mesma validação controla os destaques e o botão de confirmação.
  String? fieldError(ExtractedField field, Map<String, String> edits) {
    final value = (edits[field.key] ?? field.value?.toString() ?? '').trim();
    final blockers = issues.where(
      (issue) => issue.blocking && issue.fieldKey == field.key,
    );
    if (value.isEmpty) {
      final isRequired =
          blockers.isNotEmpty ||
          const {'amount', 'total', 'date'}.contains(field.key);
      return isRequired ? 'Preencha este campo para continuar' : null;
    }
    if (field.key == 'amount' || field.key == 'total') {
      final amount = double.tryParse(value.replaceAll(',', '.'));
      if (!RegExp(r'^\d+([.,]\d{1,2})?$').hasMatch(value) ||
          amount == null ||
          !amount.isFinite ||
          amount <= 0) {
        return 'Informe um valor positivo, como 128,90';
      }
    }
    if (field.key == 'date' || field.key == 'due_date') {
      final iso = RegExp(r'^(\d{4})-(\d{2})-(\d{2})$').firstMatch(value);
      final br = RegExp(r'^(\d{2})/(\d{2})/(\d{4})$').firstMatch(value);
      if (iso == null && br == null) return 'Informe uma data válida';
      final year = int.parse(iso?.group(1) ?? br!.group(3)!);
      final month = int.parse(iso?.group(2) ?? br!.group(2)!);
      final day = int.parse(iso?.group(3) ?? br!.group(1)!);
      final date = DateTime.utc(year, month, day);
      if (date.year != year || date.month != month || date.day != day) {
        return 'Informe uma data válida';
      }
    }
    if (blockers.isNotEmpty &&
        (!edits.containsKey(field.key) ||
            value == (field.value?.toString() ?? '').trim())) {
      return 'Corrija este campo para continuar';
    }
    return null;
  }

  bool canConfirmAfter(Map<String, String> edits) {
    if (abstained ||
        quality.quality == DocumentQuality.illegible ||
        !needsReview ||
        (fields.isEmpty && transactions.isEmpty) ||
        fields.any((field) => fieldError(field, edits) != null)) {
      return false;
    }
    return issues.where((issue) => issue.blocking).every((issue) {
      final key = issue.fieldKey;
      return key != null && fields.any((field) => field.key == key);
    });
  }
}

/// Resultado aprovado pela pessoa; o app não persiste nada nesta fase.
class ReviewedDocument {
  const ReviewedDocument({required this.fields, required this.transactions});
  final List<ExtractedField> fields;
  final List<ExtractedTransaction> transactions;
}
