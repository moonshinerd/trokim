import 'dart:async';

import 'package:flutter/foundation.dart';

import '../data/chat_repository.dart';
import '../data/conversation_store.dart';
import '../domain/chat_models.dart';
import '../domain/conversation.dart';

const String welcomeText =
    'Olá! Sou o assistente do Trokim. Posso esclarecer dúvidas sobre organização financeira, reserva de emergência e metas com base nas diretrizes oficiais do Banco Central, CVM e CFPB.';

/// Título provisório: a primeira pergunta, encurtada, enquanto o LLM não nomeia.
String placeholderTitle(String question) {
  final clean = question.replaceAll(RegExp(r'\s+'), ' ').trim();
  if (clean.length <= 40) return clean;
  final cut = clean.substring(0, 40);
  final space = cut.lastIndexOf(' ');
  return '${(space > 18 ? cut.substring(0, space) : cut).trimRight()}…';
}

class ChatController extends ChangeNotifier {
  static const int _maxTitleAttempts = 2;
  static const int _maxConversations = 200;

  final ChatRepository _repository;
  final bool _ownsRepository;
  final ConversationStore? _store;

  /// Usa o LLM local (`/chat/generate`) em vez da busca extrativa.
  bool generative;

  final List<ChatMessage> _messages = [_welcome()];
  List<Conversation> _conversations = [];
  Conversation? _current;
  bool _isLoading = false;
  bool _isDisposed = false;
  String? _failedQuestion;

  /// Com [store], as conversas são guardadas e nomeadas; sem ele, o chat
  /// funciona só em memória (uma conversa).
  ChatController({
    ChatRepository? repository,
    ConversationStore? store,
    this.generative = true,
  }) : _repository = repository ?? ChatRepository(),
       _ownsRepository = repository == null,
       _store = store;

  static ChatMessage _welcome() =>
      ChatMessage(isUser: false, text: welcomeText);

  List<ChatMessage> get messages => List.unmodifiable(_messages);
  bool get isLoading => _isLoading;
  bool get hasHistory => _store != null;
  Conversation? get current => _current;

  /// Conversas ordenadas da mais recente para a mais antiga.
  List<Conversation> get conversations => List.unmodifiable(
    [..._conversations]..sort((a, b) => b.updatedAt.compareTo(a.updatedAt)),
  );

  /// Carrega o histórico guardado no aparelho.
  Future<void> init() async {
    final store = _store;
    if (store == null) return;
    final loaded = await store.load();
    if (_isDisposed) return;
    _conversations = loaded;
    notifyListeners();
  }

  // ---------- conversas ----------

  /// Começa uma conversa nova (só é guardada quando o usuário enviar algo).
  void startNew() {
    if (_isDisposed || _isLoading) return;
    _current = null;
    _failedQuestion = null;
    _messages
      ..clear()
      ..add(_welcome());
    notifyListeners();
  }

  /// Abre uma conversa do histórico para continuar.
  void open(String id) {
    if (_isDisposed || _isLoading) return;
    final conv = _conversations.where((c) => c.id == id).firstOrNull;
    if (conv == null) return;
    _current = conv;
    _failedQuestion = null;
    _messages
      ..clear()
      ..addAll(conv.messages);
    notifyListeners();
  }

  Future<void> rename(String id, String title) async {
    final clean = title.replaceAll(RegExp(r'\s+'), ' ').trim();
    if (clean.isEmpty) return;
    _update(id, (c) => c.copyWith(title: clean, titleState: TitleState.manual));
    notifyListeners();
    await _persist();
  }

  Future<void> delete(String id) async {
    _conversations = _conversations.where((c) => c.id != id).toList();
    if (_current?.id == id) {
      _current = null;
      _failedQuestion = null;
      _messages
        ..clear()
        ..add(_welcome());
    }
    notifyListeners();
    await _persist();
  }

  // ---------- envio ----------

  Future<void> send(String text) async {
    final question = text.trim();
    if (_isDisposed || _isLoading || question.isEmpty) return;
    _failedQuestion = null;
    _messages.add(ChatMessage(isUser: true, text: question));
    _ensureConversation(question);
    await _ask(question);
  }

  Future<void> retry() async {
    final question = _failedQuestion;
    if (_isDisposed || _isLoading || question == null) return;
    _failedQuestion = null;
    if (_messages.last.isError) _messages.removeLast();
    await _ask(question);
  }

  void _ensureConversation(String question) {
    if (_store == null || _current != null) return;
    final now = DateTime.now();
    final conv = Conversation(
      id: now.microsecondsSinceEpoch.toString(),
      title: placeholderTitle(question),
      titleState: TitleState.placeholder,
      createdAt: now,
      updatedAt: now,
      messages: _messages,
    );
    _current = conv;
    _conversations = [conv, ..._conversations].take(_maxConversations).toList();
  }

  Future<void> _ask(String question) async {
    _isLoading = true;
    notifyListeners();
    ChatMessage? answer;
    try {
      final reply = await _repository.ask(question, generative: generative);
      if (_isDisposed) return;
      answer = ChatMessage(
        isUser: false,
        text: reply.answer,
        evidences: reply.evidences,
        status: reply.status,
        model: reply.model,
      );
      _messages.add(answer);
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
      if (!_isDisposed) {
        _syncCurrent();
        notifyListeners();
      }
    }
    if (_isDisposed) return;
    await _persist();
    final conv = _current;
    if (answer != null && !answer.isAbstained && conv != null) {
      unawaited(_requestTitle(conv.id, answer));
    }
  }

  // ---------- título pelo LLM ----------

  Future<void> _requestTitle(String id, ChatMessage answer) async {
    final conv = _conversations.where((c) => c.id == id).firstOrNull;
    if (conv == null ||
        conv.titleState != TitleState.placeholder ||
        conv.titleAttempts >= _maxTitleAttempts) {
      return;
    }
    _update(
      id,
      (c) => c.copyWith(
        titleState: TitleState.generating,
        titleAttempts: c.titleAttempts + 1,
      ),
    );
    notifyListeners();

    final firstQuestion = conv.messages.firstWhere((m) => m.isUser).text;
    final title = await _repository.generateTitle(
      firstQuestion,
      answer: answer.text,
    );
    if (_isDisposed) return;

    final now = _conversations.where((c) => c.id == id).firstOrNull;
    // Se foi renomeada ou apagada enquanto isso, não mexe.
    if (now == null || now.titleState != TitleState.generating) return;
    _update(
      id,
      (c) => title == null
          ? c.copyWith(titleState: TitleState.placeholder)
          : c.copyWith(title: title, titleState: TitleState.auto),
    );
    notifyListeners();
    await _persist();
  }

  // ---------- estado e persistência ----------

  void _syncCurrent() {
    final conv = _current;
    if (conv == null) return;
    _update(
      conv.id,
      (c) =>
          c.copyWith(messages: List.of(_messages), updatedAt: DateTime.now()),
    );
  }

  void _update(String id, Conversation Function(Conversation) change) {
    _conversations = [
      for (final c in _conversations) c.id == id ? change(c) : c,
    ];
    if (_current?.id == id) {
      _current = _conversations.firstWhere((c) => c.id == id);
    }
  }

  Future<void> _persist() async {
    final store = _store;
    if (store == null) return;
    try {
      await store.save(_conversations);
    } on Object {
      // Falha ao gravar não pode quebrar o chat; o estado em memória segue valendo.
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
