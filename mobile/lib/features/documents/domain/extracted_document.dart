enum DocumentKind { pixReceipt, boleto, cardInvoice, bankStatement, other }

enum DocumentQuality { legible, partial, illegible }

enum FieldSource { textLayer, ocr, vlm }

enum DocumentOrigin {
  document('documento'),
  manual('manual');

  const DocumentOrigin(this.api);
  final String api;
}

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

class DocumentStep {
  const DocumentStep({
    required this.agent,
    required this.status,
    required this.summary,
    this.durationMs = 0,
  });
  final String agent;
  final String status;
  final String summary;
  final int durationMs;

  String get agentLabel => switch (agent) {
    'document' => 'Leitura',
    'validation' => 'Validação',
    _ => agent,
  };
}

String engineLabel(String engine) {
  final parts = engine
      .split('+')
      .map((part) => part.trim().toLowerCase())
      .where((part) => part.isNotEmpty)
      .map(
        (part) => switch (part) {
          'text_layer' => 'texto do PDF',
          'vlm' || 'vision' => 'modelo de visão',
          'quality_gate' => 'verificação de qualidade',
          'manual' => 'digitação manual',
          _ when part.contains('ocr') => 'OCR local',
          _ => part,
        },
      )
      .toSet();
  return parts.isEmpty ? 'motor não informado' : parts.join(' + ');
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
    this.steps = const [],
    this.totalMs = 0,
  });

  const ExtractedDocument.manual()
    : kind = DocumentKind.other,
      bank = null,
      quality = const QualityReport(
        quality: DocumentQuality.legible,
        sharpness: 0,
        resolution: (0, 0),
      ),
      fields = const [
        ExtractedField(
          key: 'amount',
          value: null,
          confidence: 1,
          source: FieldSource.ocr,
        ),
        ExtractedField(
          key: 'date',
          value: null,
          confidence: 1,
          source: FieldSource.ocr,
        ),
        ExtractedField(
          key: 'counterparty',
          value: null,
          confidence: 1,
          source: FieldSource.ocr,
        ),
      ],
      transactions = const [],
      issues = const [],
      needsReview = true,
      abstained = false,
      reason = null,
      engine = 'manual',
      steps = const [],
      totalMs = 0;

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
  final List<DocumentStep> steps;
  final int totalMs;

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
  const ReviewedDocument({
    required this.fields,
    required this.transactions,
    this.kind = DocumentKind.other,
    this.bank,
    this.origin = DocumentOrigin.document,
    this.confirmation,
  });
  final List<ExtractedField> fields;
  final List<ExtractedTransaction> transactions;
  final DocumentKind kind;
  final String? bank;
  final DocumentOrigin origin;
  final DocumentConfirmation? confirmation;

  ReviewedDocument withConfirmation(DocumentConfirmation value) =>
      ReviewedDocument(
        fields: fields,
        transactions: transactions,
        kind: kind,
        bank: bank,
        origin: origin,
        confirmation: value,
      );

  String? _text(String key) {
    for (final field in fields) {
      if (field.key != key) continue;
      final value = field.value?.toString().trim() ?? '';
      return value.isEmpty ? null : value;
    }
    return null;
  }

  Map<String, Object?> toConfirmBody() {
    final amount =
        reviewedAmount(_text('amount')) ??
        reviewedAmount(_text('total')) ??
        _linesTotal();
    final dueDate = reviewedDate(_text('due_date'));
    final lineDates = transactions
        .map((line) => line.date)
        .whereType<DateTime>()
        .map(_isoDate);
    final date =
        reviewedDate(_text('date')) ??
        dueDate ??
        (lineDates.isEmpty ? null : lineDates.first);
    final bankName = _text('bank') ?? bank;
    final description = _text('counterparty') ?? bankName ?? _kindDescription();
    return {
      'kind': _kindApi(),
      'date': date,
      'amount': amount,
      'description': _limit(description, 120),
      'due_date': ?dueDate,
      if (bankName != null) 'bank': _limit(bankName, 60),
      'transactions': [
        for (final line in transactions)
          if ((line.amount ?? 0) > 0 && line.description.trim().isNotEmpty)
            {
              'date': line.date == null ? date : _isoDate(line.date!),
              'description': _limit(line.description.trim(), 120),
              'amount': line.amount!.toStringAsFixed(2),
            },
      ],
      'origin': origin.api,
    };
  }

  String? _linesTotal() {
    final total = transactions.fold<double>(
      0,
      (sum, line) => sum + ((line.amount ?? 0) > 0 ? line.amount! : 0),
    );
    return total > 0 ? total.toStringAsFixed(2) : null;
  }

  String _kindApi() => switch (kind) {
    DocumentKind.pixReceipt => 'pix_receipt',
    DocumentKind.boleto => 'boleto',
    DocumentKind.cardInvoice => 'card_invoice',
    DocumentKind.bankStatement => 'bank_statement',
    DocumentKind.other => 'other',
  };

  String _kindDescription() => switch (kind) {
    DocumentKind.pixReceipt => 'Comprovante Pix',
    DocumentKind.boleto => 'Boleto',
    DocumentKind.cardInvoice => 'Fatura de cartão',
    DocumentKind.bankStatement => 'Extrato bancário',
    DocumentKind.other =>
      origin == DocumentOrigin.manual
          ? 'Lançamento digitado'
          : 'Documento lido',
  };

  static String _limit(String value, int max) =>
      value.length <= max ? value : value.substring(0, max).trimRight();
}

String _isoDate(DateTime date) =>
    '${date.year.toString().padLeft(4, '0')}-'
    '${date.month.toString().padLeft(2, '0')}-'
    '${date.day.toString().padLeft(2, '0')}';

String? reviewedAmount(String? value) {
  final text = value?.trim() ?? '';
  if (!RegExp(r'^\d+([.,]\d{1,2})?$').hasMatch(text)) return null;
  final amount = double.tryParse(text.replaceAll(',', '.'));
  if (amount == null || !amount.isFinite || amount <= 0) return null;
  return amount.toStringAsFixed(2);
}

String? reviewedDate(String? value) {
  final text = value?.trim() ?? '';
  final iso = RegExp(r'^(\d{4})-(\d{2})-(\d{2})$').firstMatch(text);
  final br = RegExp(r'^(\d{2})/(\d{2})/(\d{4})$').firstMatch(text);
  if (iso == null && br == null) return null;
  final year = int.parse(iso?.group(1) ?? br!.group(3)!);
  final month = int.parse(iso?.group(2) ?? br!.group(2)!);
  final day = int.parse(iso?.group(3) ?? br!.group(1)!);
  final date = DateTime.utc(year, month, day);
  if (date.year != year || date.month != month || date.day != day) {
    return null;
  }
  return _isoDate(date);
}

class DocumentConfirmation {
  const DocumentConfirmation({
    required this.outcome,
    required this.uid,
    required this.accountId,
    required this.message,
    this.uids = const [],
  });

  factory DocumentConfirmation.fromJson(Map<String, dynamic> json) =>
      DocumentConfirmation(
        outcome: json['outcome']?.toString() ?? 'criado',
        uid: json['uid']?.toString() ?? '',
        accountId: json['account_id']?.toString() ?? '',
        message: json['message']?.toString() ?? 'Lançamento salvo.',
        uids: [
          for (final uid in json['uids'] as List? ?? const []) uid.toString(),
        ],
      );

  final String outcome;
  final String uid;
  final String accountId;
  final String message;
  final List<String> uids;
}
