import 'package:flutter/foundation.dart';

import '../data/document_repository.dart';
import '../domain/extracted_document.dart';

class DocumentReviewController extends ChangeNotifier {
  DocumentReviewController(this.repository);
  final DocumentRepository repository;
  ExtractedDocument? _document;
  bool _loading = false;
  String? _error;
  bool _disposed = false;

  ExtractedDocument? get document => _document;
  bool get loading => _loading;
  String? get error => _error;

  void reset() {
    if (_disposed || _loading) return;
    _document = null;
    _error = null;
    notifyListeners();
  }

  Future<void> read(String name, List<int> bytes) async {
    if (_disposed || _loading) return;
    _loading = true;
    _document = null;
    _error = null;
    notifyListeners();
    try {
      final result = await repository.extract(name, bytes);
      if (!_disposed) _document = result;
    } catch (_) {
      if (!_disposed) {
        _error = 'Não foi possível ler o documento. Tente novamente.';
      }
    } finally {
      if (!_disposed) {
        _loading = false;
        notifyListeners();
      }
    }
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
