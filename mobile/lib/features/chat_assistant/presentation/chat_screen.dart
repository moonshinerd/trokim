import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';
import '../domain/chat_models.dart';
import 'chat_controller.dart';
import 'evidence_card.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key, this.controller});

  final ChatController? controller;

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  late ChatController _chat;
  bool _auditMode = false;

  @override
  void initState() {
    super.initState();
    _chat = widget.controller ?? ChatController();
    _chat.addListener(_scrollToLatest);
  }

  void _scrollToLatest() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && _scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _sendMessage() {
    final text = _textController.text.trim();
    if (text.isEmpty || _chat.isLoading) return;
    _textController.clear();
    _chat.send(text);
  }

  @override
  void dispose() {
    _chat.removeListener(_scrollToLatest);
    if (widget.controller == null) _chat.dispose();
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Assistente Trokim'),
        actions: [
          Row(mainAxisSize: MainAxisSize.min, children: [
            const Text('Auditoria', style: TextStyle(fontSize: 12)),
            Semantics(
              label: 'Modo de auditoria pedagógica',
              child: Switch(
                value: _auditMode,
                onChanged: (value) => setState(() => _auditMode = value),
                activeThumbColor: Colors.white,
              ),
            ),
          ]),
        ],
      ),
      body: AnimatedBuilder(
        animation: _chat,
        builder: (context, _) => Column(
          children: [
            if (_auditMode)
              Container(
                width: double.infinity,
                margin: const EdgeInsets.fromLTRB(12, 10, 12, 0),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFEFF6FF),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFFBFDBFE)),
                ),
                child: const Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.fact_check_outlined,
                          color: AppTheme.primaryBlue, size: 19),
                      SizedBox(width: 8),
                      Expanded(
                          child: Text(
                        'Auditoria pedagógica: respostas fundamentadas exibem as fontes e os trechos recuperados. O Trokim não fabrica um comparativo sem evidências.',
                        style: TextStyle(fontSize: 12, height: 1.4),
                      )),
                    ]),
              ),
            Expanded(
              child: LayoutBuilder(
                builder: (context, constraints) => ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.all(16),
                  itemCount: _chat.messages.length + (_chat.isLoading ? 1 : 0),
                  itemBuilder: (context, index) {
                    if (index == _chat.messages.length) {
                      return const Padding(
                        padding: EdgeInsets.symmetric(vertical: 12),
                        child: Row(
                          children: [
                            SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            ),
                            SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                'Consultando fontes e gerando resposta...',
                              ),
                            ),
                          ],
                        ),
                      );
                    }
                    final message = _chat.messages[index];
                    return _MessageBubble(
                      message: message,
                      maxWidth: constraints.maxWidth * 0.82,
                      onRetry:
                          index == _chat.messages.length - 1 && !_chat.isLoading
                              ? _chat.retry
                              : null,
                      auditMode: _auditMode,
                      onQuickQuestion: (question) {
                        _textController.text = question;
                        _textController.selection = TextSelection.collapsed(
                          offset: question.length,
                        );
                        _sendMessage();
                      },
                    );
                  },
                ),
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              color: Colors.white,
              child: SafeArea(
                top: false,
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _textController,
                        enabled: !_chat.isLoading,
                        maxLength: 1000,
                        minLines: 1,
                        maxLines: 3,
                        textInputAction: TextInputAction.send,
                        decoration: const InputDecoration(
                          hintText: 'Pergunte sobre orçamento ou reserva...',
                          border: InputBorder.none,
                        ),
                        onSubmitted: (_) => _sendMessage(),
                      ),
                    ),
                    IconButton(
                      tooltip: 'Enviar',
                      icon: const Icon(Icons.send),
                      color: AppTheme.primaryBlue,
                      onPressed: _chat.isLoading ? null : _sendMessage,
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({
    required this.message,
    required this.maxWidth,
    this.onRetry,
    required this.auditMode,
    this.onQuickQuestion,
  });

  final ChatMessage message;
  final double maxWidth;
  final VoidCallback? onRetry;
  final bool auditMode;
  final ValueChanged<String>? onQuickQuestion;

  @override
  Widget build(BuildContext context) {
    final color = message.isUser
        ? AppTheme.primaryBlue
        : message.isError
            ? Colors.red.shade50
            : message.isAbstained
                ? Theme.of(context).colorScheme.surfaceContainerHighest
                : Colors.white;
    return Align(
      alignment: message.isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(14),
        constraints: BoxConstraints(maxWidth: maxWidth),
        decoration: BoxDecoration(
          color: color,
          borderRadius: BorderRadius.circular(14),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.04),
              blurRadius: 4,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (message.isAbstained || message.isError) ...[
              Icon(
                message.isError
                    ? Icons.error_outline
                    : Icons.warning_amber_rounded,
                color: message.isError ? AppTheme.dangerRed : Colors.blueGrey,
                semanticLabel: message.isError
                    ? 'Erro de conexão'
                    : 'Sem evidências suficientes',
              ),
              const SizedBox(height: 8),
            ],
            Text(
              message.text,
              style: TextStyle(
                color: message.isUser ? Colors.white : AppTheme.textDark,
                fontSize: 14,
                height: 1.4,
              ),
            ),
            if (message.isAbstained)
              Padding(
                padding: const EdgeInsets.only(top: 10),
                child: Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFFF7E6),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Text(
                    'Risco de especulação: não há evidências oficiais suficientes para responder com segurança.',
                    style: TextStyle(fontSize: 12, height: 1.35),
                  ),
                ),
              ),
            if (message.isAbstained) ...[
              const SizedBox(height: 8),
              Wrap(spacing: 4, runSpacing: 0, children: [
                _QuickQuestion(
                    label: 'Reserva de emergência',
                    onPressed: () => onQuickQuestion
                        ?.call('Como começar uma reserva de emergência?')),
                _QuickQuestion(
                    label: 'Organizar o orçamento',
                    onPressed: () => onQuickQuestion
                        ?.call('Como organizar meu orçamento mensal?')),
              ]),
            ],
            if (auditMode &&
                !message.isUser &&
                !message.isError &&
                message.status != null)
              _AuditComparison(message: message),
            if (message.isError && onRetry != null)
              TextButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh),
                label: const Text('Tentar novamente'),
              ),
            if (!message.isUser && !message.isError && !message.isAbstained)
              for (final evidence in message.evidences) ...[
                const SizedBox(height: 8),
                EvidenceCard(evidence: evidence),
              ],
          ],
        ),
      ),
    );
  }
}

class _QuickQuestion extends StatelessWidget {
  const _QuickQuestion({required this.label, required this.onPressed});
  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) => ActionChip(
        label: Text(label, style: const TextStyle(fontSize: 11)),
        onPressed: onPressed,
        visualDensity: VisualDensity.compact,
      );
}

class _AuditComparison extends StatelessWidget {
  const _AuditComparison({required this.message});
  final ChatMessage message;

  @override
  Widget build(BuildContext context) {
    final grounded = message.status == AssistantStatus.grounded;
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFFE2E8F0)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Comparativo de transparência',
            style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12)),
        const SizedBox(height: 8),
        _AuditRow(
          icon: grounded ? Icons.verified : Icons.warning_amber_rounded,
          color: grounded ? const Color(0xFF168447) : Colors.blueGrey,
          title: grounded ? 'Com RAG' : 'Com RAG: abstenção ética',
          body: grounded
              ? 'Resposta vinculada às fontes oficiais abaixo.'
              : 'O sistema não encontrou evidências suficientes para orientar.',
        ),
        const SizedBox(height: 7),
        const _AuditRow(
          icon: Icons.link_off,
          color: AppTheme.primaryBlue,
          title: 'Sem lastro verificável',
          body:
              'Nenhuma resposta alternativa é apresentada: sem fontes, um palpite poderia induzir a uma decisão financeira inadequada.',
        ),
      ]),
    );
  }
}

class _AuditRow extends StatelessWidget {
  const _AuditRow(
      {required this.icon,
      required this.color,
      required this.title,
      required this.body});
  final IconData icon;
  final Color color;
  final String title;
  final String body;

  @override
  Widget build(BuildContext context) => Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 16),
          const SizedBox(width: 6),
          Expanded(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title,
                  style: TextStyle(
                      fontWeight: FontWeight.w600, color: color, fontSize: 11)),
              Text(body, style: const TextStyle(fontSize: 11, height: 1.35)),
            ]),
          ),
        ],
      );
}
