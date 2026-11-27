import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../../../core/network/api_client.dart';
import '../data/document_repository.dart';
import '../domain/extracted_document.dart';

class DocumentReviewController extends ChangeNotifier {
  DocumentReviewController(this.repository);
  final DocumentRepository repository;
  ExtractedDocument? _document;
  bool _loading = false;
  String? _error;
  bool _needsConsent = false;
  bool _confirming = false;
  String? _confirmError;
  bool _disposed = false;

  static const networkMessage =
      'Sem conexão com a API. Confira o endereço em Ajustes e tente novamente.';

  ExtractedDocument? get document => _document;
  bool get loading => _loading;
  String? get error => _error;
  bool get needsConsent => _needsConsent;
  bool get confirming => _confirming;
  String? get confirmError => _confirmError;

  void reset() {
    if (_disposed || _loading || _confirming) return;
    _document = null;
    _error = null;
    _needsConsent = false;
    _confirmError = null;
    notifyListeners();
  }

  Future<void> read(
    String name,
    List<int> bytes, {
    String engine = 'ocr',
    bool allowRemote = false,
  }) async {
    if (_disposed || _loading || _confirming) return;
    _loading = true;
    _document = null;
    _error = null;
    _needsConsent = false;
    _confirmError = null;
    notifyListeners();
    try {
      final result = await repository.extract(
        name,
        bytes,
        engine: engine,
        allowRemote: engine == 'vision' && allowRemote,
      );
      if (!_disposed) _document = result;
    } catch (error) {
      if (!_disposed) {
        _needsConsent = error is ApiException && error.statusCode == 403;
        _error = _readMessage(error);
      }
    } finally {
      if (!_disposed) {
        _loading = false;
        notifyListeners();
      }
    }
  }

  Future<DocumentConfirmation?> confirm(ReviewedDocument reviewed) async {
    if (_disposed || _loading || _confirming) return null;
    _confirming = true;
    _confirmError = null;
    notifyListeners();
    try {
      final result = await repository.confirm(reviewed);
      return _disposed ? null : result;
    } catch (error) {
      if (!_disposed) _confirmError = _confirmMessage(error);
      return null;
    } finally {
      if (!_disposed) {
        _confirming = false;
        notifyListeners();
      }
    }
  }

  static bool _offline(Object error) =>
      error is http.ClientException || error is TimeoutException;

  static String _readMessage(Object error) {
    if (_offline(error)) return networkMessage;
    if (error is! ApiException) {
      return 'Não foi possível ler o documento. Tente novamente.';
    }
    final detail = error.detail?.trim();
    final message = detail == null || detail.isEmpty ? null : detail;
    return switch (error.statusCode) {
      413 =>
        '${message ?? 'O arquivo é grande demais.'} '
            'Escolha um arquivo menor ou tire outra foto.',
      415 => message ?? 'Envie uma foto JPEG ou PNG, ou um PDF.',
      422 =>
        '${message ?? 'Não foi possível abrir o arquivo.'} '
            'Confira o arquivo ou escolha outro documento.',
      503 =>
        '${message ?? 'O motor de leitura está indisponível.'} '
            'Tente de novo em instantes ou digite os dados à mão.',
      403 =>
        '${message ?? 'O motor de visão é remoto e precisa do seu consentimento.'} '
            'Autorize em Ajustes ou leia com o OCR local.',
      _ => message ?? 'Não foi possível ler o documento. Tente novamente.',
    };
  }

  static String _confirmMessage(Object error) {
    if (_offline(error)) return networkMessage;
    if (error is ApiException) {
      final detail = error.detail?.trim();
      if (detail != null && detail.isNotEmpty) return detail;
      if (error.statusCode == 422) {
        return 'O validador bloqueou este lançamento; corrija os campos.';
      }
    }
    return 'Não foi possível salvar o lançamento. Tente novamente.';
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
