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

  ApiClient({
    this.baseUrl = ApiConstants.defaultBaseUrl,
    http.Client? client,
    this.timeout = const Duration(seconds: 15),
  }) : _client = client ?? http.Client();

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
