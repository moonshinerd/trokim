import 'package:flutter/foundation.dart';

import '../data/chat_repository.dart';
import '../domain/chat_models.dart';

class ChatController extends ChangeNotifier {
  final ChatRepository _repository;
  final bool _ownsRepository;
  final List<ChatMessage> _messages = [
    ChatMessage(
      isUser: false,
      text:
          'Olá! Sou o assistente do Trokim. Posso esclarecer dúvidas sobre organização financeira, reserva de emergência e metas com base nas diretrizes oficiais do Banco Central, CVM e CFPB.',
    ),
  ];
  bool _isLoading = false;
  bool _isDisposed = false;
  String? _failedQuestion;

  ChatController({ChatRepository? repository})
      : _repository = repository ?? ChatRepository(),
        _ownsRepository = repository == null;

  List<ChatMessage> get messages => List.unmodifiable(_messages);
  bool get isLoading => _isLoading;

  Future<void> send(String text) async {
    final question = text.trim();
    if (_isDisposed || _isLoading || question.isEmpty) return;
    _failedQuestion = null;
    _messages.add(ChatMessage(isUser: true, text: question));
    await _ask(question);
  }

  Future<void> retry() async {
    final question = _failedQuestion;
    if (_isDisposed || _isLoading || question == null) return;
    _failedQuestion = null;
    if (_messages.last.isError) _messages.removeLast();
    await _ask(question);
  }

  Future<void> _ask(String question) async {
    _isLoading = true;
    notifyListeners();
    try {
      final reply = await _repository.ask(question);
      if (_isDisposed) return;
      _messages.add(
        ChatMessage(
          isUser: false,
          text: reply.answer,
          evidences: reply.evidences,
          status: reply.status,
        ),
      );
    } catch (error) {
      if (_isDisposed) return;
      _failedQuestion = question;
      _messages.add(
        ChatMessage(
          isUser: false,
          text: error is ChatException
              ? error.message
              : 'Não foi possível consultar o assistente. Tente novamente.',
          isError: true,
        ),
      );
    } finally {
      _isLoading = false;
      if (!_isDisposed) notifyListeners();
    }
  }

  @override
  void dispose() {
    if (_isDisposed) return;
    _isDisposed = true;
    if (_ownsRepository) _repository.close();
    super.dispose();
  }
}
