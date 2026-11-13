import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../constants/api_constants.dart';

class ApiException implements Exception {
  final int statusCode;

  const ApiException(this.statusCode);
}

class ApiClient {
  final String baseUrl;
  final http.Client _client;
  final Duration timeout;
  final Duration generationTimeout;
  final Set<Completer<void>> _generationAborts = {};

  ApiClient({
    this.baseUrl = ApiConstants.defaultBaseUrl,
    http.Client? client,
    this.timeout = const Duration(seconds: 15),
    this.generationTimeout = const Duration(
      seconds: ApiConstants.chatGenerateTimeoutSeconds,
    ),
  }) : _client = client ?? http.Client() {
    if (generationTimeout <= Duration.zero) {
      throw ArgumentError.value(generationTimeout, 'generationTimeout');
    }
  }

  Future<Map<String, dynamic>> getSummary() async {
    final response = await _client
        .get(Uri.parse('$baseUrl${ApiConstants.transactionsSummaryEndpoint}'))
        .timeout(timeout);
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

  Future<Map<String, dynamic>> generateAssistant(String message) async {
    final abort = Completer<void>();
    _generationAborts.add(abort);
    final request = http.AbortableRequest(
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
      final response = await http.Response.fromStream(await _client.send(request));
      return _decode(response);
    } on http.RequestAbortedException {
      if (timedOut) {
        throw TimeoutException('Tempo limite da geração excedido.', generationTimeout);
      }
      rethrow;
    } finally {
      timer.cancel();
      _generationAborts.remove(abort);
    }
  }

  Map<String, dynamic> _decode(http.Response response) {
    if (response.statusCode != 200) {
      throw ApiException(response.statusCode);
    }
    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
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
