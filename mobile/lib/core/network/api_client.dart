import 'dart:convert';
import 'package:http/http.dart' as http;
import '../constants/api_constants.dart';

class ApiClient {
  final String baseUrl;

  ApiClient({this.baseUrl = ApiConstants.defaultBaseUrl});

  Future<Map<String, dynamic>> getSummary() async {
    final response = await http.get(
      Uri.parse('$baseUrl${ApiConstants.transactionsSummaryEndpoint}'),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Falha ao obter resumo: ${response.statusCode}');
  }

  Future<Map<String, dynamic>> askAssistant(String message) async {
    final response = await http.post(
      Uri.parse('$baseUrl${ApiConstants.chatAskEndpoint}'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'message': message}),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Falha na consulta ao assistente: ${response.statusCode}');
  }
}
