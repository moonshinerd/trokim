import 'package:flutter/foundation.dart';

import '../data/document_repository.dart';
import '../domain/extracted_document.dart';

class DocumentReviewController extends ChangeNotifier {
  DocumentReviewController(this.repository);
  final DocumentRepository repository;
  ExtractedDocument? document;
  bool loading = false;
  String? error;

  Future<void> read(String name, List<int> bytes) async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      document = await repository.extract(name, bytes);
    } catch (_) {
      error = 'Não foi possível ler o documento. Verifique sua conexão e tente novamente.';
    } finally {
      loading = false;
      notifyListeners();
    }
  }
}
