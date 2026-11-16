import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../constants/api_constants.dart';

class ApiException implements Exception {
  final int statusCode;

  /// Mensagem de erro devolvida pela API (campo `detail`), quando houver.
  final String? detail;

  const ApiException(this.statusCode, [this.detail]);
}

class ApiClient {
  final String? _fixedBaseUrl;
  final String Function()? _baseUrlProvider;
  final http.Client _client;
  final Duration timeout;

  /// Ler e interpretar um extrato (principalmente PDF) leva mais que um GET.
  final Duration uploadTimeout;
  final Duration generationTimeout;

  /// Nomear a conversa com o LLM local não pode travar o chat.
  final Duration titleTimeout;
  final Set<Completer<void>> _generationAborts = {};

  /// [baseUrlProvider] é consultado a cada chamada, para que o endereço
  /// editado em Ajustes valha sem recriar o cliente.
  ApiClient({
    String? baseUrl,
    String Function()? baseUrlProvider,
    http.Client? client,
    this.timeout = const Duration(seconds: 15),
    this.uploadTimeout = const Duration(seconds: 60),
    this.titleTimeout = const Duration(seconds: 40),
    this.generationTimeout = const Duration(
      seconds: ApiConstants.chatGenerateTimeoutSeconds,
    ),
  }) : _fixedBaseUrl = baseUrl,
       _baseUrlProvider = baseUrlProvider,
       _client = client ?? http.Client() {
    if (generationTimeout <= Duration.zero) {
      throw ArgumentError.value(generationTimeout, 'generationTimeout');
    }
  }

  String get baseUrl =>
      _baseUrlProvider?.call() ?? _fixedBaseUrl ?? ApiConstants.defaultBaseUrl;

  Future<Map<String, dynamic>> getSummary() async {
    final response = await _client
        .get(Uri.parse('$baseUrl${ApiConstants.transactionsSummaryEndpoint}'))
        .timeout(timeout);
    return _decode(response);
  }

  Future<List<Map<String, dynamic>>> getTransactions() async {
    final response = await _client
        .get(Uri.parse('$baseUrl${ApiConstants.transactionsEndpoint}'))
        .timeout(timeout);
    final decoded = _decodeJson(response);
    if (decoded is! List) {
      throw const FormatException('Resposta inválida do servidor.');
    }
    return [
      for (final item in decoded)
        if (item is Map<String, dynamic>)
          item
        else
          throw const FormatException('Resposta inválida do servidor.'),
    ];
  }

  /// Envia um extrato (OFX ou PDF) para a API local processar.
  Future<Map<String, dynamic>> uploadStatement(
    String filename,
    List<int> bytes,
  ) async {
    final request =
        http.MultipartRequest(
            'POST',
            Uri.parse('$baseUrl${ApiConstants.transactionsUploadEndpoint}'),
          )
          ..files.add(
            http.MultipartFile.fromBytes('file', bytes, filename: filename),
          );
    final response = await http.Response.fromStream(
      await _client.send(request).timeout(uploadTimeout),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> askAssistant(String message) async {
    final response = await _client
        .post(
          Uri.parse('$baseUrl${ApiConstants.chatAskEndpoint}'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'message': message}),
        )
        .timeout(timeout);
    return _decode(response);
  }

  /// Pede ao LLM local um título curto para a conversa.
  Future<Map<String, dynamic>> generateTitle(
    String message, {
    String? answer,
  }) async {
    final response = await _client
        .post(
          Uri.parse('$baseUrl${ApiConstants.chatTitleEndpoint}'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'message': message,
            if (answer != null && answer.isNotEmpty) 'answer': answer,
          }),
        )
        .timeout(titleTimeout);
    return _decode(response);
  }

  Future<Map<String, dynamic>> generateAssistant(String message) async {
    final abort = Completer<void>();
    _generationAborts.add(abort);
    final request =
        http.AbortableRequest(
            'POST',
            Uri.parse('$baseUrl${ApiConstants.chatGenerateEndpoint}'),
            abortTrigger: abort.future,
          )
          ..headers['Content-Type'] = 'application/json'
          ..body = jsonEncode({'message': message, 'mode': 'grounded'});
    var timedOut = false;
    final timer = Timer(generationTimeout, () {
      timedOut = true;
      if (!abort.isCompleted) abort.complete();
    });
    try {
      final response = await http.Response.fromStream(
        await _client.send(request),
      );
      return _decode(response);
    } on http.RequestAbortedException {
      if (timedOut) {
        throw TimeoutException(
          'Tempo limite da geração excedido.',
          generationTimeout,
        );
      }
      rethrow;
    } finally {
      timer.cancel();
      _generationAborts.remove(abort);
    }
  }

  Object? _decodeJson(http.Response response) {
    if (response.statusCode != 200) {
      throw ApiException(response.statusCode, _detailOf(response));
    }
    return jsonDecode(utf8.decode(response.bodyBytes));
  }

  String? _detailOf(http.Response response) {
    try {
      final body = jsonDecode(utf8.decode(response.bodyBytes));
      if (body is Map && body['detail'] is String) {
        return body['detail'] as String;
      }
    } on Object {
      // Corpo que não é JSON: segue sem detalhe.
    }
    return null;
  }

  Map<String, dynamic> _decode(http.Response response) {
    final decoded = _decodeJson(response);
    if (decoded is! Map<String, dynamic>) {
      throw const FormatException('Resposta inválida do servidor.');
    }
    return decoded;
  }

  void close() {
    for (final abort in _generationAborts) {
      if (!abort.isCompleted) abort.complete();
    }
    _client.close();
  }
}
