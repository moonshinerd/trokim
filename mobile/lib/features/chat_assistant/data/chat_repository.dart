import 'dart:async';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../../../core/network/api_client.dart';
import '../domain/chat_models.dart';

class ChatException implements Exception {
  final String message;

  const ChatException(this.message);

  @override
  String toString() => message;
}

class ChatRepository {
  final ApiClient _apiClient;

  ChatRepository({ApiClient? apiClient})
    : _apiClient = apiClient ?? ApiClient();

  /// Pede um título curto ao LLM. Devolve `null` se a API não conseguir
  /// (o app mantém o título provisório; nunca mostra erro por isso).
  Future<String?> generateTitle(String message, {String? answer}) async {
    try {
      final json = await _apiClient.generateTitle(message, answer: answer);
      final title = (json['title'] as String?)?.trim();
      return (title == null || title.isEmpty) ? null : title;
    } on Object {
      return null;
    }
  }

  /// Consulta o assistente. Com [generative] (padrão), o LLM local redige a
  /// resposta (`/chat/generate`); sem ele, só a busca extrativa (`/chat/ask`).
  Future<AssistantReply> ask(String message, {bool generative = true}) async {
    try {
      if (!generative) {
        return AssistantReply.fromExtractiveJson(
          await _apiClient.askAssistant(message),
        );
      }
      return AssistantReply.fromJson(
        await _apiClient.generateAssistant(message),
      );
    } on TimeoutException {
      throw const ChatException(
        'O assistente demorou para responder. Tente novamente.',
      );
    } on SocketException {
      throw const ChatException(
        'Não foi possível conectar ao assistente. Verifique sua conexão e se o backend está disponível.',
      );
    } on http.ClientException {
      throw const ChatException(
        'Não foi possível conectar ao assistente. Verifique sua conexão e se o backend está disponível.',
      );
    } on ApiException catch (error) {
      if (error.statusCode == 422) {
        throw const ChatException(
          'Envie uma pergunta entre 1 e 1000 caracteres.',
        );
      }
      throw const ChatException(
        'O assistente está indisponível no momento. Tente novamente.',
      );
    } on FormatException {
      throw const ChatException(
        'O assistente enviou uma resposta inválida. Tente novamente.',
      );
    } on TypeError {
      throw const ChatException(
        'O assistente enviou uma resposta inválida. Tente novamente.',
      );
    }
  }

  void close() => _apiClient.close();
}
