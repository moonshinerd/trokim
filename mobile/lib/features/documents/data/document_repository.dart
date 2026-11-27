import '../../../core/network/api_client.dart';
import '../domain/extracted_document.dart';

abstract interface class DocumentRepository {
  Future<ExtractedDocument> extract(
    String filename,
    List<int> bytes, {
    String engine = 'ocr',
    bool allowRemote = false,
  });

  Future<DocumentConfirmation> confirm(ReviewedDocument reviewed);
}

class ApiDocumentRepository implements DocumentRepository {
  ApiDocumentRepository(this._newClient);

  final ApiClient Function() _newClient;

  Future<T> _run<T>(Future<T> Function(ApiClient client) action) async {
    final client = _newClient();
    try {
      return await action(client);
    } finally {
      client.close();
    }
  }

  @override
  Future<ExtractedDocument> extract(
    String filename,
    List<int> bytes, {
    String engine = 'ocr',
    bool allowRemote = false,
  }) => _run(
    (client) async => documentFromResponse(
      await client.extractDocument(
        filename,
        bytes,
        engine: engine,
        allowRemote: engine == 'vision' && allowRemote,
      ),
    ),
  );

  @override
  Future<DocumentConfirmation> confirm(ReviewedDocument reviewed) => _run(
    (client) async => DocumentConfirmation.fromJson(
      await client.confirmDocument(reviewed.toConfirmBody()),
    ),
  );
}

ExtractedDocument documentFromResponse(Map<String, dynamic> json) {
  final raw = _map(json['document']);
  final source = raw.isEmpty ? json : raw;
  final quality = _map(source['quality']);
  final abstained = source['abstained'] == true;
  final transactions = [
    for (final item in _list(source['transactions']))
      ExtractedTransaction(
        date: DateTime.tryParse(item['date']?.toString() ?? ''),
        description: item['description']?.toString() ?? '',
        amount: _double(item['amount']),
        installment: item['installment']?.toString(),
        confidence: _double(item['confidence']) ?? 0,
      ),
  ];
  final fields = [
    for (final item in _list(source['fields']))
      ExtractedField(
        key: item['key']?.toString() ?? '',
        value: item['value'],
        confidence: _double(item['confidence']) ?? 0,
        source: _source(item['source']),
      ),
  ];
  final rawIssues = json.containsKey('validation_issues')
      ? _list(json['validation_issues'])
      : _list(source['issues']);
  final issues = [
    for (final item in rawIssues)
      ValidationIssue(
        code: item['code']?.toString() ?? '',
        message: item['message']?.toString() ?? '',
        blocking: item['severity'] == 'blocker',
        fieldKey: _issueField(
          item['code']?.toString() ?? '',
          item['message']?.toString() ?? '',
          fields,
        ),
      ),
  ];
  if (!abstained && (fields.isNotEmpty || transactions.isNotEmpty)) {
    final keys = fields.map((field) => field.key).toSet();
    void addEmpty(String key) {
      if (keys.add(key)) {
        fields.add(
          ExtractedField(
            key: key,
            value: null,
            confidence: 0,
            source: fields.isEmpty ? FieldSource.ocr : fields.first.source,
          ),
        );
      }
    }

    for (final issue in issues) {
      final key = issue.fieldKey;
      if (issue.blocking && key != null) addEmpty(key);
    }
    final hasLineAmount = transactions.any((line) => (line.amount ?? 0) > 0);
    if (!keys.contains('amount') && !keys.contains('total') && !hasLineAmount) {
      addEmpty('amount');
    }
    final hasLineDate = transactions.any((line) => line.date != null);
    if (!keys.contains('date') && !keys.contains('due_date') && !hasLineDate) {
      addEmpty('date');
    }
  }
  final resolution = _list(quality['resolution'], raw: true);
  return ExtractedDocument(
    kind: _kind(source['kind']),
    bank: source['bank']?.toString(),
    quality: QualityReport(
      quality: switch (quality['quality']) {
        'legible' => DocumentQuality.legible,
        'illegible' => DocumentQuality.illegible,
        _ => DocumentQuality.partial,
      },
      sharpness: _double(quality['sharpness']) ?? 0,
      resolution: (
        resolution.isNotEmpty ? (_double(resolution[0]) ?? 0).round() : 0,
        resolution.length > 1 ? (_double(resolution[1]) ?? 0).round() : 0,
      ),
      meanOcrConfidence: _double(quality['mean_ocr_confidence']),
      reasons: [
        for (final reason in _list(quality['reasons'], raw: true))
          reason.toString(),
      ],
    ),
    fields: fields,
    transactions: transactions,
    issues: issues,
    abstained: abstained,
    reason: source['reason']?.toString(),
    engine: source['engine']?.toString() ?? '',
    steps: [
      for (final item in _list(json['steps']))
        DocumentStep(
          agent: item['agent']?.toString() ?? '',
          status: item['status']?.toString() ?? '',
          summary: item['summary']?.toString() ?? '',
          durationMs: (_double(item['duration_ms']) ?? 0).round(),
        ),
    ],
    totalMs: (_double(json['total_ms']) ?? 0).round(),
  );
}

String? _issueField(String code, String message, List<ExtractedField> fields) {
  final text = message.toLowerCase();
  bool has(String key) => fields.any((field) => field.key == key);
  if (text.contains('(due_date)') ||
      text.contains('vencimento') ||
      code == 'DUE_BEFORE_ISSUE') {
    return 'due_date';
  }
  if (text.contains('(total_amount)') || code == 'TOTAL_MISMATCH') {
    return 'total';
  }
  if (text.contains('(amount)')) return 'amount';
  if (text.contains('(issue_date)') || text.contains('(date)')) return 'date';
  if (text.contains('(recipient)')) return 'counterparty';
  if (text.contains('(institution)')) return 'bank';
  if (code == 'AMOUNT_FORMAT') return has('total') ? 'total' : 'amount';
  if (code == 'DATE_INVALID' && !text.contains('item')) return 'date';
  return null;
}

Map<String, dynamic> _map(Object? value) =>
    value is Map ? value.cast<String, dynamic>() : <String, dynamic>{};

List<dynamic> _list(Object? value, {bool raw = false}) {
  if (value is! List) return const [];
  if (raw) return value;
  return [
    for (final item in value)
      if (item is Map) item.cast<String, dynamic>(),
  ];
}

double? _double(Object? value) => switch (value) {
  final num number => number.toDouble(),
  final String text => double.tryParse(text),
  _ => null,
};

FieldSource _source(Object? value) => switch (value) {
  'text_layer' => FieldSource.textLayer,
  'vlm' => FieldSource.vlm,
  _ => FieldSource.ocr,
};

DocumentKind _kind(Object? value) => switch (value) {
  'pix_receipt' => DocumentKind.pixReceipt,
  'boleto' => DocumentKind.boleto,
  'card_invoice' => DocumentKind.cardInvoice,
  'bank_statement' => DocumentKind.bankStatement,
  _ => DocumentKind.other,
};
