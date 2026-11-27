import 'dart:async';
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:material_ui/material_ui.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/network/api_client.dart';
import '../../../core/settings/settings_controller.dart';
import '../../finance/presentation/finance_controller.dart';
import '../data/document_repository.dart';
import '../domain/extracted_document.dart';
import 'document_review_controller.dart';

class DocumentSelection {
  const DocumentSelection({
    required this.name,
    required this.bytes,
    required this.isImage,
  });
  final String name;
  final List<int> bytes;
  final bool isImage;
}

typedef DocumentPicker = Future<DocumentSelection?> Function();

class DocumentImportScreen extends StatefulWidget {
  const DocumentImportScreen({
    super.key,
    this.repository,
    this.cameraPicker,
    this.galleryPicker,
    this.pdfPicker,
  });
  final DocumentRepository? repository;
  final DocumentPicker? cameraPicker;
  final DocumentPicker? galleryPicker;
  final DocumentPicker? pdfPicker;
  @override
  State<DocumentImportScreen> createState() => _DocumentImportScreenState();
}

class _DocumentImportScreenState extends State<DocumentImportScreen> {
  late final SettingsController _settings =
      SettingsScope.read(context) ?? SettingsController.memory();
  late final controller = DocumentReviewController(
    widget.repository ??
        ApiDocumentRepository(
          () => ApiClient(baseUrlProvider: () => _settings.apiBaseUrl),
        ),
  );
  final picker = ImagePicker();
  DocumentSelection? selection;
  final edits = <String, String>{};
  final removedLines = <int>{};
  bool _selecting = false;
  bool _manual = false;

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  Future<DocumentSelection?> _image(ImageSource source) async {
    final file = await picker.pickImage(source: source);
    if (file == null) return null;
    return DocumentSelection(
      name: file.name,
      bytes: await file.readAsBytes(),
      isImage: true,
    );
  }

  Future<DocumentSelection?> _pdf() async {
    final file = await FilePicker.pickFile(
      type: FileType.custom,
      allowedExtensions: ['pdf'],
    );
    if (file == null) return null;
    return DocumentSelection(
      name: file.name,
      bytes: await file.readAsBytes(),
      isImage: false,
    );
  }

  Future<void> _select(DocumentPicker picker) async {
    if (_selecting || controller.loading) return;
    _selecting = true;
    try {
      final selected = await picker();
      if (selected == null || !mounted) return;
      setState(() {
        selection = selected;
        _manual = false;
        edits.clear();
        removedLines.clear();
      });
      controller.reset();
    } catch (_) {
      if (mounted) _message('Não foi possível abrir a câmera ou o seletor.');
    } finally {
      _selecting = false;
    }
  }

  Future<void> _chooseAnother() async {
    final source = await showModalBottomSheet<int>(
      context: context,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.camera_alt_outlined),
              title: const Text('Fotografar'),
              onTap: () => Navigator.pop(context, 0),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_outlined),
              title: const Text('Escolher imagem'),
              onTap: () => Navigator.pop(context, 1),
            ),
            ListTile(
              leading: const Icon(Icons.picture_as_pdf_outlined),
              title: const Text('Escolher PDF'),
              onTap: () => Navigator.pop(context, 2),
            ),
          ],
        ),
      ),
    );
    if (!mounted || source == null) return;
    final documentPicker = switch (source) {
      0 => widget.cameraPicker ?? () => _image(ImageSource.camera),
      1 => widget.galleryPicker ?? () => _image(ImageSource.gallery),
      _ => widget.pdfPicker ?? _pdf,
    };
    await _select(documentPicker);
  }

  void _message(String value) =>
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(value)));

  Future<void> _read({bool localOnly = false}) async {
    final selected = selection;
    if (selected == null) return;
    final engine = localOnly
        ? SettingsController.ocrEngine
        : _settings.documentEngine;
    await controller.read(
      selected.name,
      selected.bytes,
      engine: engine,
      allowRemote: !localOnly && _settings.allowRemoteDocuments,
    );
  }

  void _typeManually() {
    if (controller.loading || controller.confirming) return;
    setState(() {
      _manual = true;
      edits.clear();
      removedLines.clear();
    });
    controller.reset();
  }

  Future<void> _confirm(ExtractedDocument doc, DocumentOrigin origin) async {
    final reviewed = ReviewedDocument(
      fields: doc.fields
          .map(
            (field) => ExtractedField(
              key: field.key,
              value: edits[field.key] ?? field.value,
              confidence: field.confidence,
              source: field.source,
            ),
          )
          .toList(growable: false),
      transactions: doc.transactions.indexed
          .where((entry) => !removedLines.contains(entry.$1))
          .map((entry) => entry.$2)
          .toList(growable: false),
      kind: doc.kind,
      bank: doc.bank,
      origin: origin,
    );
    final result = await controller.confirm(reviewed);
    if (result == null || !mounted) return;
    final finance = FinanceScope.read(context);
    if (finance != null) {
      await finance.saveToDevice();
      unawaited(finance.load());
    }
    if (!mounted) return;
    _message(result.message);
    Navigator.pop(context, reviewed.withConfirmation(result));
  }

  String get _engineText =>
      _settings.documentEngine == SettingsController.visionEngine
      ? _settings.remoteConsent
            ? 'Motor de leitura: modelo de visão. Com o consentimento salvo em Ajustes, a imagem pode sair do aparelho para o provedor remoto.'
            : 'Motor de leitura: modelo de visão, sem envio a provedor remoto.'
      : 'Motor de leitura: OCR local (escolha em Ajustes).';

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Importar documento')),
    body: AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        final doc = controller.document;
        if (_manual) {
          return _review(
            const ExtractedDocument.manual(),
            DocumentOrigin.manual,
          );
        }
        if (selection == null) return _entry();
        if (controller.loading) {
          return const Center(
            child: CircularProgressIndicator(semanticsLabel: 'Lendo documento'),
          );
        }
        if (controller.error != null) return _error();
        if (doc == null) return _preview();
        if (doc.abstained || doc.quality.quality == DocumentQuality.illegible) {
          return _unreadable(doc);
        }
        return _review(doc, DocumentOrigin.document);
      },
    ),
  );

  Widget _entry() => _status([
    const Icon(Icons.document_scanner_outlined, size: 56),
    const SizedBox(height: 16),
    const Text(
      'Fotografar ou escolher documento',
      style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
    ),
    const SizedBox(height: 12),
    const Text(
      'O arquivo vai para a API do Trokim configurada em Ajustes. Nada é salvo antes de você revisar e confirmar. Fotos podem permanecer no cache temporário do sistema.',
      textAlign: TextAlign.center,
    ),
    const SizedBox(height: 8),
    Text(_engineText, textAlign: TextAlign.center),
    const SizedBox(height: 20),
    FilledButton.icon(
      onPressed: () =>
          _select(widget.cameraPicker ?? () => _image(ImageSource.camera)),
      icon: const Icon(Icons.camera_alt_outlined),
      label: const Text('Fotografar'),
    ),
    TextButton.icon(
      onPressed: () =>
          _select(widget.galleryPicker ?? () => _image(ImageSource.gallery)),
      icon: const Icon(Icons.photo_library_outlined),
      label: const Text('Escolher imagem'),
    ),
    TextButton.icon(
      onPressed: () => _select(widget.pdfPicker ?? _pdf),
      icon: const Icon(Icons.picture_as_pdf_outlined),
      label: const Text('Escolher PDF'),
    ),
    TextButton.icon(
      onPressed: _typeManually,
      icon: const Icon(Icons.edit_outlined),
      label: const Text('Digitar os dados à mão'),
    ),
  ]);

  Widget _preview() => ListView(
    padding: const EdgeInsets.all(20),
    children: [
      const Text(
        'Pré-visualização',
        style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
      ),
      const SizedBox(height: 12),
      if (selection!.isImage)
        ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: Image.memory(
            Uint8List.fromList(selection!.bytes),
            height: 360,
            fit: BoxFit.contain,
            errorBuilder: (_, _, _) => const SizedBox(
              height: 180,
              child: Center(child: Icon(Icons.image_outlined, size: 56)),
            ),
          ),
        )
      else
        const ListTile(
          leading: Icon(Icons.picture_as_pdf),
          title: Text('Documento PDF selecionado'),
        ),
      const SizedBox(height: 12),
      Text(selection!.name),
      Text(_engineText),
      const Text(
        'Fotos podem permanecer no cache temporário do sistema; o app não as adiciona à biblioteca.',
      ),
      const SizedBox(height: 16),
      OutlinedButton.icon(
        onPressed: _chooseAnother,
        icon: const Icon(Icons.refresh),
        label: const Text('Escolher outro documento'),
      ),
      FilledButton(onPressed: _read, child: const Text('Ler documento')),
    ],
  );

  Widget _error() => _status([
    const Icon(Icons.error_outline, size: 52),
    const SizedBox(height: 12),
    Text(controller.error!, textAlign: TextAlign.center),
    const SizedBox(height: 16),
    FilledButton(onPressed: _read, child: const Text('Tentar novamente')),
    if (controller.needsConsent)
      TextButton(
        onPressed: () => _read(localOnly: true),
        child: const Text('Ler com OCR local'),
      ),
    OutlinedButton.icon(
      onPressed: _chooseAnother,
      icon: const Icon(Icons.refresh),
      label: const Text('Escolher outro documento'),
    ),
    TextButton(
      onPressed: _typeManually,
      child: const Text('Digitar os dados à mão'),
    ),
  ]);

  Widget _trail(ExtractedDocument doc) => Card(
    margin: const EdgeInsets.symmetric(vertical: 12),
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Como li este documento',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 4),
          Text('Lido por ${engineLabel(doc.engine)}'),
          ...doc.steps.map(
            (step) => Text(
              '${step.agentLabel}: ${step.summary} (${step.durationMs} ms)',
            ),
          ),
          if (doc.totalMs > 0) Text('Tempo total: ${doc.totalMs} ms'),
        ],
      ),
    ),
  );

  Widget _unreadable(ExtractedDocument doc) => _status([
    const Icon(Icons.document_scanner_outlined, size: 52),
    const Text(
      'Não conseguimos ler este documento',
      style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
    ),
    Text(doc.reason ?? 'A imagem não permitiu uma leitura confiável.'),
    ...doc.quality.reasons
        .where((reason) => reason != doc.reason)
        .map(Text.new),
    const SizedBox(height: 16),
    const Text(
      'Enquadre o documento inteiro, use boa iluminação e evite reflexos.',
    ),
    FilledButton.icon(
      onPressed: () =>
          _select(widget.cameraPicker ?? () => _image(ImageSource.camera)),
      icon: const Icon(Icons.camera_alt_outlined),
      label: const Text('Tirar outra foto'),
    ),
    TextButton(
      onPressed: _typeManually,
      child: const Text('Digitar os dados à mão'),
    ),
    _trail(doc),
  ]);

  Widget _review(ExtractedDocument doc, DocumentOrigin origin) => ListView(
    padding: const EdgeInsets.all(20),
    children: [
      Text(
        origin == DocumentOrigin.manual
            ? 'Digite os dados do lançamento'
            : 'Confira o que o Trokim leu',
        style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
      ),
      const SizedBox(height: 8),
      const Text(
        'Revise e corrija os campos. Ao confirmar, o lançamento é criado com os valores desta tela.',
      ),
      if (origin == DocumentOrigin.document) _trail(doc),
      const SizedBox(height: 12),
      ...doc.fields.map((field) {
        final key = field.key;
        final confidence = field.confidence;
        final fieldIssues = doc.issues.where((i) => i.fieldKey == key).toList();
        final error = doc.fieldError(field, edits);
        final uncertain = confidence < .65 || fieldIssues.isNotEmpty;
        return Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: TextFormField(
            key: ValueKey(key),
            initialValue: field.value?.toString() ?? '',
            decoration: InputDecoration(
              labelText: _label(key),
              helperText:
                  'Confiança: ${_confidence(confidence)}${fieldIssues.map((issue) => ' • ${issue.message}').join()}',
              helperMaxLines: 5,
              errorText: error,
              filled: uncertain || error != null,
              fillColor: error != null
                  ? Theme.of(context).colorScheme.errorContainer
                  : Theme.of(context).colorScheme.tertiaryContainer,
              prefixIcon: Icon(
                uncertain || error != null
                    ? Icons.warning_amber_rounded
                    : Icons.check_circle_outline,
              ),
              border: const OutlineInputBorder(),
            ),
            onChanged: (text) => setState(() => edits[key] = text),
          ),
        );
      }),
      ...doc.issues
          .where(
            (issue) => !doc.fields.any((field) => field.key == issue.fieldKey),
          )
          .map(
            (issue) => ListTile(
              leading: Icon(
                issue.blocking ? Icons.error_outline : Icons.info_outline,
              ),
              title: Text(issue.message),
            ),
          ),
      if (doc.transactions.isNotEmpty) ...[
        const Text(
          'Linhas da fatura',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
        ),
        ...doc.transactions.indexed
            .where((e) => !removedLines.contains(e.$1))
            .map(
              (e) => ListTile(
                title: Text(e.$2.description),
                subtitle: Text(e.$2.amount?.toStringAsFixed(2) ?? ''),
                trailing: IconButton(
                  tooltip: 'Excluir linha',
                  icon: const Icon(Icons.delete_outline),
                  onPressed: () => setState(() => removedLines.add(e.$1)),
                ),
              ),
            ),
      ],
      if (controller.confirmError != null)
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Text(
            controller.confirmError!,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        ),
      FilledButton(
        onPressed: doc.canConfirmAfter(edits) && !controller.confirming
            ? () => _confirm(doc, origin)
            : null,
        child: Text(controller.confirming ? 'Salvando…' : 'Confirmar'),
      ),
      TextButton(
        onPressed: controller.confirming ? null : () => Navigator.pop(context),
        child: const Text('Descartar'),
      ),
    ],
  );

  Widget _status(List<Widget> children) => LayoutBuilder(
    builder: (context, constraints) => SingleChildScrollView(
      child: ConstrainedBox(
        constraints: BoxConstraints(minHeight: constraints.maxHeight),
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(mainAxisSize: MainAxisSize.min, children: children),
          ),
        ),
      ),
    ),
  );

  String _label(String key) => switch (key) {
    'amount' => 'Valor',
    'date' => 'Data',
    'counterparty' => 'Favorecido',
    'bank' => 'Banco',
    'due_date' => 'Vencimento',
    'total' => 'Total',
    'document_id' => 'Identificação do documento',
    _ => key,
  };
  String _confidence(double value) => value >= .85
      ? 'alta'
      : value >= .65
      ? 'média'
      : 'baixa — confira';
}
