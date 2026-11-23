import 'dart:async';

import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:trokim/core/theme/app_theme.dart';
import 'package:trokim/features/documents/data/document_repository.dart';
import 'package:trokim/features/documents/domain/extracted_document.dart';
import 'package:trokim/features/documents/presentation/document_import_screen.dart';

const _readable = ExtractedDocument(
  kind: DocumentKind.cardInvoice,
  bank: 'Banco Sintético',
  quality: QualityReport(
    quality: DocumentQuality.partial,
    sharpness: .9,
    resolution: (800, 1200),
  ),
  fields: [
    ExtractedField(
      key: 'amount',
      value: '128.90',
      confidence: .95,
      source: FieldSource.ocr,
    ),
    ExtractedField(
      key: 'counterparty',
      value: 'Mercado Exemplo',
      confidence: .42,
      source: FieldSource.ocr,
    ),
    ExtractedField(
      key: 'due_date',
      value: null,
      confidence: .2,
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

class _Repo implements DocumentRepository {
  _Repo(this.result);
  final FutureOr<ExtractedDocument> Function(List<int> bytes) result;
  @override
  Future<ExtractedDocument> extract(String filename, List<int> bytes) async =>
      result(bytes);
}

Widget _app({
  required DocumentRepository repo,
  required DocumentPicker camera,
  DocumentPicker? gallery,
  DocumentPicker? pdf,
  ValueChanged<Object?>? onResult,
}) => MaterialApp(
  theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: Colors.teal)),
  darkTheme: ThemeData.dark(),
  home: Builder(
    builder: (context) => Scaffold(
      body: TextButton(
        onPressed: () async {
          final result = await Navigator.of(context).push<Object?>(
            MaterialPageRoute(
              builder: (_) => DocumentImportScreen(
                repository: repo,
                cameraPicker: camera,
                galleryPicker: gallery,
                pdfPicker: pdf,
              ),
            ),
          );
          onResult?.call(result);
        },
        child: const Text('Abrir importação'),
      ),
    ),
  ),
);

Future<void> _chooseAndRead(WidgetTester tester) async {
  await tester.tap(find.text('Fotografar'));
  await tester.pumpAndSettle();
  expect(find.text('Pré-visualização'), findsOneWidget);
  await tester.tap(find.text('Ler documento'));
  await tester.pumpAndSettle();
}

void main() {
  test(
    'cores de leitura destacada mantêm contraste nos temas claro e escuro',
    () {
      for (final theme in [AppTheme.lightTheme, AppTheme.darkTheme]) {
        final colors = theme.colorScheme;
        expect(
          _contrast(colors.error, colors.errorContainer),
          greaterThanOrEqualTo(4.5),
        );
        expect(
          _contrast(colors.onSurface, colors.tertiaryContainer),
          greaterThanOrEqualTo(4.5),
        );
      }
    },
  );

  testWidgets('foto legível abre revisão e só confirma após toque explícito', (
    tester,
  ) async {
    Object? result;
    await tester.pumpWidget(
      _app(
        repo: _Repo((_) => _readable),
        camera: () async => const DocumentSelection(
          name: 'comprovante-sintetico.png',
          bytes: [1, 2],
          isImage: true,
        ),
        onResult: (value) => result = value,
      ),
    );
    await tester.tap(find.text('Abrir importação'));
    await tester.pumpAndSettle();
    await _chooseAndRead(tester);
    expect(find.text('Confira o que o Trokim leu'), findsOneWidget);
    expect(find.textContaining('Confiança: baixa'), findsOneWidget);
    expect(find.text('Compra sintética'), findsOneWidget);
    expect(
      tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, 'Confirmar'))
          .onPressed,
      isNull,
    );
    expect(result, isNull);
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Vencimento'),
      '30/11/2026',
    );
    await tester.pump();
    expect(
      tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, 'Confirmar'))
          .onPressed,
      isNotNull,
    );
    await tester.ensureVisible(find.byTooltip('Excluir linha'));
    await tester.tap(find.byTooltip('Excluir linha'));
    await tester.pump();
    await tester.ensureVisible(find.widgetWithText(FilledButton, 'Confirmar'));
    await tester.tap(find.text('Confirmar'));
    await tester.pumpAndSettle();
    expect(result, isA<ReviewedDocument>());
    final reviewed = result! as ReviewedDocument;
    expect(
      reviewed.fields.singleWhere((field) => field.key == 'due_date').value,
      '30/11/2026',
    );
    expect(reviewed.transactions, isEmpty);
  });

  testWidgets('documento legível aceita campo opcional vazio sem persistir', (
    tester,
  ) async {
    Object? result;
    await tester.pumpWidget(
      _app(
        repo: _Repo(
          (_) => ExtractedDocument(
            kind: DocumentKind.pixReceipt,
            quality: const QualityReport(
              quality: DocumentQuality.legible,
              sharpness: .9,
              resolution: (1200, 1800),
            ),
            fields: [
              _readable.fields.first,
              const ExtractedField(
                key: 'document_id',
                value: null,
                confidence: .9,
                source: FieldSource.ocr,
              ),
            ],
            engine: 'mock',
          ),
        ),
        camera: () async => const DocumentSelection(
          name: 'pix-sintetico.png',
          bytes: [1],
          isImage: true,
        ),
        onResult: (value) => result = value,
      ),
    );
    await tester.tap(find.text('Abrir importação'));
    await tester.pumpAndSettle();
    await _chooseAndRead(tester);
    expect(result, isNull);
    await tester.ensureVisible(find.widgetWithText(FilledButton, 'Confirmar'));
    await tester.tap(find.text('Confirmar'));
    await tester.pumpAndSettle();
    expect(result, isA<ReviewedDocument>());
  });

  testWidgets('cancelar o seletor não inicia leitura', (tester) async {
    var calls = 0;
    await tester.pumpWidget(
      _app(
        repo: _Repo((_) {
          calls++;
          return _readable;
        }),
        camera: () async => null,
      ),
    );
    await tester.tap(find.text('Abrir importação'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Fotografar'));
    await tester.pumpAndSettle();
    expect(find.text('Pré-visualização'), findsNothing);
    expect(calls, 0);
  });

  testWidgets('sair durante a leitura ignora a resposta tardia', (
    tester,
  ) async {
    final pending = Completer<ExtractedDocument>();
    await tester.pumpWidget(
      _app(
        repo: _Repo((_) => pending.future),
        camera: () async => const DocumentSelection(
          name: 'pix-sintetico.png',
          bytes: [1],
          isImage: true,
        ),
      ),
    );
    await tester.tap(find.text('Abrir importação'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Fotografar'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Ler documento'));
    await tester.pump();
    await tester.pageBack();
    await tester.pumpAndSettle();
    pending.complete(_readable);
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('Abrir importação'), findsOneWidget);
  });

  testWidgets('erro do seletor após sair da tela não usa contexto descartado', (
    tester,
  ) async {
    final pending = Completer<DocumentSelection?>();
    await tester.pumpWidget(
      _app(repo: _Repo((_) => _readable), camera: () => pending.future),
    );
    await tester.tap(find.text('Abrir importação'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Fotografar'));
    await tester.pageBack();
    await tester.pumpAndSettle();
    pending.completeError(Exception('permissão negada'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });

  testWidgets('descartar fecha a revisão sem devolver campos', (tester) async {
    Object? result = 'pendente';
    await tester.pumpWidget(
      _app(
        repo: _Repo((_) => _readable),
        camera: () async => const DocumentSelection(
          name: 'comprovante-sintetico.png',
          bytes: [1, 2],
          isImage: true,
        ),
        onResult: (value) => result = value,
      ),
    );
    await tester.tap(find.text('Abrir importação'));
    await tester.pumpAndSettle();
    await _chooseAndRead(tester);
    await tester.tap(find.text('Descartar'));
    await tester.pumpAndSettle();
    expect(result, isNull);
  });

  testWidgets('prévia permite trocar imagem por outro documento', (
    tester,
  ) async {
    await tester.pumpWidget(
      _app(
        repo: _Repo((_) => _readable),
        camera: () async => const DocumentSelection(
          name: 'comprovante-sintetico.png',
          bytes: [1, 2],
          isImage: true,
        ),
        pdf: () async => const DocumentSelection(
          name: 'fatura-sintetica.pdf',
          bytes: [3, 4],
          isImage: false,
        ),
      ),
    );
    await tester.tap(find.text('Abrir importação'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Fotografar'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Escolher outro documento'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Escolher PDF').last);
    await tester.pumpAndSettle();
    expect(find.text('Documento PDF selecionado'), findsOneWidget);
  });

  testWidgets('ilegível oferece tirar outra foto', (tester) async {
    var picks = 0;
    const unreadable = ExtractedDocument(
      kind: DocumentKind.other,
      quality: QualityReport(
        quality: DocumentQuality.illegible,
        sharpness: .1,
        resolution: (300, 300),
        reasons: ['Imagem desfocada'],
      ),
      fields: [],
      abstained: true,
      reason: 'Imagem desfocada',
      engine: 'mock',
    );
    await tester.pumpWidget(
      _app(
        repo: _Repo((_) => unreadable),
        camera: () async {
          picks++;
          return const DocumentSelection(
            name: 'imagem-sintetica.png',
            bytes: [],
            isImage: true,
          );
        },
      ),
    );
    await tester.tap(find.text('Abrir importação'));
    await tester.pumpAndSettle();
    await _chooseAndRead(tester);
    expect(find.text('Não conseguimos ler este documento'), findsOneWidget);
    expect(find.text('Imagem desfocada'), findsOneWidget);
    await tester.tap(find.text('Tirar outra foto'));
    await tester.pumpAndSettle();
    expect(picks, 2);
  });

  testWidgets('erro do repositório permite nova tentativa', (tester) async {
    var attempts = 0;
    await tester.pumpWidget(
      _app(
        repo: _Repo((_) {
          attempts++;
          if (attempts == 1) throw Exception('offline');
          return _readable;
        }),
        camera: () async => const DocumentSelection(
          name: 'doc-sintetico.png',
          bytes: [4],
          isImage: true,
        ),
      ),
    );
    await tester.tap(find.text('Abrir importação'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Fotografar'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Ler documento'));
    await tester.pumpAndSettle();
    expect(find.text('Tentar novamente'), findsOneWidget);
    await tester.tap(find.text('Tentar novamente'));
    await tester.pumpAndSettle();
    expect(find.text('Confira o que o Trokim leu'), findsOneWidget);
  });
}

double _contrast(Color foreground, Color background) {
  final a = foreground.computeLuminance();
  final b = background.computeLuminance();
  return (a > b ? a + .05 : b + .05) / (a > b ? b + .05 : a + .05);
}
