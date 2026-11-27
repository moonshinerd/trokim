import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:trokim/features/documents/data/document_repository.dart';
import 'package:trokim/features/documents/domain/extracted_document.dart';
import 'package:trokim/features/documents/presentation/document_review_controller.dart';

ExtractedDocument _document({
  List<ExtractedField> fields = const [],
  List<ValidationIssue> issues = const [],
}) => ExtractedDocument(
  kind: DocumentKind.pixReceipt,
  quality: const QualityReport(
    quality: DocumentQuality.legible,
    sharpness: .9,
    resolution: (1200, 1800),
  ),
  fields: fields,
  issues: issues,
  engine: 'mock',
);

ExtractedField _field(String key, String? value) => ExtractedField(
  key: key,
  value: value,
  confidence: .9,
  source: FieldSource.ocr,
);

class _PendingRepository implements DocumentRepository {
  final result = Completer<ExtractedDocument>();
  int calls = 0;

  @override
  Future<ExtractedDocument> extract(
    String filename,
    List<int> bytes, {
    String engine = 'ocr',
    bool allowRemote = false,
  }) {
    calls++;
    return result.future;
  }

  @override
  Future<DocumentConfirmation> confirm(ReviewedDocument reviewed) async {
    return const DocumentConfirmation(
      outcome: 'criado',
      uid: 'doc-sintetico',
      accountId: 'documentos',
      message: 'Lançamento criado.',
    );
  }
}

void main() {
  test(
    'campos opcionais vazios não impedem confirmar um documento legível',
    () {
      final doc = _document(
        fields: [_field('amount', '128.90'), _field('document_id', null)],
      );
      expect(doc.canConfirm, isTrue);
      expect(doc.canConfirmAfter({'document_id': ''}), isTrue);
    },
  );

  test(
    'um bloqueio exige corrigir o valor mesmo quando já está preenchido',
    () {
      final doc = _document(
        fields: [_field('amount', '128.90')],
        issues: const [
          ValidationIssue(
            code: 'VALUE_INVALID',
            message: 'Confira o valor.',
            blocking: true,
            fieldKey: 'amount',
          ),
        ],
      );
      expect(doc.canConfirm, isFalse);
      expect(doc.canConfirmAfter({'amount': '128.90'}), isFalse);
      expect(doc.canConfirmAfter({'amount': ' 128.90 '}), isFalse);
      expect(doc.canConfirmAfter({'amount': '129,90'}), isTrue);
    },
  );

  test('avisos não bloqueantes não escondem bloqueios do mesmo campo', () {
    final doc = _document(
      fields: [_field('due_date', null)],
      issues: const [
        ValidationIssue(
          code: 'LOW_CONFIDENCE',
          message: 'Confira a data.',
          blocking: false,
          fieldKey: 'due_date',
        ),
        ValidationIssue(
          code: 'FIELD_MISSING',
          message: 'Informe a data.',
          blocking: true,
          fieldKey: 'due_date',
        ),
      ],
    );
    expect(doc.canConfirm, isFalse);
    expect(doc.fieldError(doc.fields.single, {}), isNotNull);
    expect(doc.canConfirmAfter({'due_date': '30/11/2026'}), isTrue);
  });

  test('datas impossíveis e valores inválidos continuam bloqueados', () {
    final amount = _document(fields: [_field('amount', '128.90')]);
    for (final value in ['', 'abc', '-1', '0', 'NaN', 'Infinity', '1.234']) {
      expect(amount.canConfirmAfter({'amount': value}), isFalse, reason: value);
    }
    final date = _document(fields: [_field('date', '2026-11-23')]);
    for (final value in ['abc', '31/02/2026', '2026-02-31', '2026-13-01']) {
      expect(date.canConfirmAfter({'date': value}), isFalse, reason: value);
    }
    expect(date.canConfirmAfter({'date': '29/02/2028'}), isTrue);
  });

  test('documento vazio e bloqueios sem campo editável não são liberados', () {
    expect(_document().canConfirm, isFalse);
    for (final key in [null, 'campo_ausente']) {
      final doc = _document(
        fields: [_field('amount', '128.90')],
        issues: [
          ValidationIssue(
            code: 'DOCUMENT_INVALID',
            message: 'Escolha outro documento.',
            blocking: true,
            fieldKey: key,
          ),
        ],
      );
      expect(doc.canConfirmAfter({'amount': '129.90'}), isFalse);
    }
  });

  test(
    'leitura concluída após sair da tela não notifica controlador descartado',
    () async {
      final repo = _PendingRepository();
      final controller = DocumentReviewController(repo);
      var notifications = 0;
      controller.addListener(() => notifications++);
      final reading = controller.read('sintetico.png', [1]);
      expect(controller.loading, isTrue);
      controller.dispose();
      repo.result.complete(_document(fields: [_field('amount', '128.90')]));
      await reading;
      expect(notifications, 1);
      expect(controller.document, isNull);
    },
  );

  test('erro após descarte também é ignorado', () async {
    final repo = _PendingRepository();
    final controller = DocumentReviewController(repo);
    final reading = controller.read('sintetico.png', [1]);
    controller.dispose();
    repo.result.completeError(Exception('falha simulada'));
    await reading;
    expect(controller.error, isNull);
  });

  test(
    'leitura não duplica requisição e reset limpa o resultado anterior',
    () async {
      final repo = _PendingRepository();
      final controller = DocumentReviewController(repo);
      addTearDown(controller.dispose);
      final reading = controller.read('sintetico.png', [1]);
      await controller.read('sintetico.png', [1]);
      expect(repo.calls, 1);
      repo.result.complete(_document(fields: [_field('amount', '128.90')]));
      await reading;
      expect(controller.document, isNotNull);
      expect(controller.loading, isFalse);
      controller.reset();
      expect(controller.document, isNull);
      expect(controller.error, isNull);
    },
  );
}
