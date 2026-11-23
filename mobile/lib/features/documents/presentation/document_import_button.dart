import 'package:material_ui/material_ui.dart';

import '../domain/extracted_document.dart';
import 'document_import_screen.dart';

/// Entrada comum para a revisão simulada; a persistência pertence à integração #97.
class DocumentImportButton extends StatelessWidget {
  const DocumentImportButton({super.key});

  @override
  Widget build(BuildContext context) => OutlinedButton.icon(
    onPressed: () => Navigator.of(context).push<ReviewedDocument>(
      MaterialPageRoute(builder: (_) => const DocumentImportScreen()),
    ),
    icon: const Icon(Icons.document_scanner_outlined),
    label: const Text('Fotografar ou escolher documento'),
  );
}
