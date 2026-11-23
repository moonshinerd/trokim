import '../domain/extracted_document.dart';

abstract interface class DocumentRepository {
  Future<ExtractedDocument> extract(String filename, List<int> bytes);
}

/// Implementação temporária para desenvolver a revisão antes da API #97.
class FakeDocumentRepository implements DocumentRepository {
  @override
  Future<ExtractedDocument> extract(String filename, List<int> bytes) async {
    await Future<void>.delayed(const Duration(milliseconds: 250));
    if (bytes.isEmpty) {
      return const ExtractedDocument(
        kind: DocumentKind.other,
        quality: QualityReport(
          quality: DocumentQuality.illegible,
          sharpness: 0,
          resolution: (0, 0),
          reasons: ['Imagem desfocada ou sem texto legível.'],
        ),
        fields: [],
        abstained: true,
        reason: 'A imagem está desfocada ou não contém texto legível.',
        engine: 'mock',
      );
    }
    return const ExtractedDocument(
      kind: DocumentKind.cardInvoice,
      bank: 'Banco Sintético',
      quality: QualityReport(
        quality: DocumentQuality.partial,
        sharpness: 0.92,
        resolution: (1200, 1800),
        meanOcrConfidence: 0.82,
      ),
      fields: [
        ExtractedField(
          key: 'amount',
          value: '128.90',
          confidence: .97,
          source: FieldSource.ocr,
        ),
        ExtractedField(
          key: 'date',
          value: '2026-11-23',
          confidence: .84,
          source: FieldSource.ocr,
        ),
        ExtractedField(
          key: 'counterparty',
          value: 'Mercado Exemplo',
          confidence: .58,
          source: FieldSource.ocr,
        ),
        ExtractedField(
          key: 'bank',
          value: 'Banco Sintético',
          confidence: .95,
          source: FieldSource.ocr,
        ),
        ExtractedField(
          key: 'due_date',
          value: null,
          confidence: .15,
          source: FieldSource.ocr,
        ),
      ],
      transactions: [
        ExtractedTransaction(
          description: 'Compra sintética',
          amount: 128.90,
          confidence: .88,
        ),
      ],
      issues: [
        ValidationIssue(
          code: 'LOW_CONFIDENCE',
          message: 'Confira o favorecido.',
          blocking: false,
          fieldKey: 'counterparty',
        ),
        ValidationIssue(
          code: 'FIELD_MISSING',
          message: 'Informe o vencimento.',
          blocking: true,
          fieldKey: 'due_date',
        ),
      ],
      engine: 'mock',
    );
  }
}
