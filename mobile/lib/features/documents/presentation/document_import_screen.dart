import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:material_ui/material_ui.dart';
import 'package:image_picker/image_picker.dart';

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
  late final controller = DocumentReviewController(
    widget.repository ?? FakeDocumentRepository(),
  );
  final picker = ImagePicker();
  DocumentSelection? selection;
  final edits = <String, String>{};
  final removedLines = <int>{};
  bool _selecting = false;

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

  Future<void> _read() async {
    final selected = selection;
    if (selected == null) return;
    await controller.read(selected.name, selected.bytes);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Importar documento')),
    body: AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        final doc = controller.document;
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
        return _review(doc);
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
      'Leitura simulada com dados sintéticos. Nenhum lançamento será salvo. Fotos podem permanecer no cache temporário do sistema.',
      textAlign: TextAlign.center,
    ),
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
      const Text(
        'A leitura é simulada. Fotos podem permanecer no cache temporário do sistema; o app não as adiciona à biblioteca.',
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
    Text(controller.error!),
    FilledButton(onPressed: _read, child: const Text('Tentar novamente')),
  ]);

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
  ]);

  Widget _review(ExtractedDocument doc) => ListView(
    padding: const EdgeInsets.all(20),
    children: [
      const Text(
        'Confira o que o Trokim leu',
        style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
      ),
      const SizedBox(height: 8),
      const Text(
        'Revise e corrija os campos. Confirmar conclui esta simulação, sem salvar lançamentos.',
      ),
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
      FilledButton(
        onPressed: doc.canConfirmAfter(edits)
            ? () {
                _message('Revisão concluída. Nenhum lançamento foi salvo.');
                Navigator.pop(
                  context,
                  ReviewedDocument(
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
                  ),
                );
              }
            : null,
        child: const Text('Confirmar'),
      ),
      TextButton(
        onPressed: () => Navigator.pop(context),
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
