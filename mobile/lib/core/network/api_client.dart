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

  /// O LLM local pode levar dezenas de segundos na primeira resposta.
  final Duration generativeTimeout;
  final Duration titleTimeout;

  ApiClient({
    this.baseUrl = ApiConstants.defaultBaseUrl,
    http.Client? client,
    this.timeout = const Duration(seconds: 15),
    this.generativeTimeout = const Duration(seconds: 150),
    this.titleTimeout = const Duration(seconds: 40),
  }) : _client = client ?? http.Client();

  Future<Map<String, dynamic>> getSummary() async {
    final response = await _client
        .get(Uri.parse('$baseUrl${ApiConstants.transactionsSummaryEndpoint}'))
        .timeout(timeout);
    return _decode(response);
  }

  /// Consulta o assistente. Com [generative], usa o LLM local
  /// (`/chat/generate`), que é mais lento; senão, a busca extrativa (`/chat/ask`).
  Future<Map<String, dynamic>> askAssistant(
    String message, {
    bool generative = false,
  }) async {
    final response = await _client
        .post(
          Uri.parse(
            '$baseUrl${generative ? ApiConstants.chatGenerateEndpoint : ApiConstants.chatAskEndpoint}',
          ),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'message': message}),
        )
        .timeout(generative ? generativeTimeout : timeout);
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

  void close() => _client.close();
}
