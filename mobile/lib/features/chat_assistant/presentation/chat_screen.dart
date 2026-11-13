import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/app_motion.dart';
import '../../../core/widgets/trokim_logo.dart';
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
        title: const Row(children: [
          TrokimMark(size: 30),
          SizedBox(width: 10),
          Flexible(
            child: Text('Assistente',
                maxLines: 1, overflow: TextOverflow.ellipsis),
          ),
        ]),
        actions: [
          Row(mainAxisSize: MainAxisSize.min, children: [
            const Text('Auditoria',
                style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
            Semantics(
              label: 'Modo de auditoria pedagógica',
              child: Switch(
                value: _auditMode,
                onChanged: (value) => setState(() => _auditMode = value),
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
                margin: const EdgeInsets.fromLTRB(16, 4, 16, 0),
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: context.colors.tint,
                  borderRadius: BorderRadius.circular(18),
                ),
                child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.fact_check_outlined,
                          color: context.colors.accent, size: 19),
                      SizedBox(width: 8),
                      Expanded(
                          child: Text(
                        'Auditoria pedagógica: respostas fundamentadas exibem as fontes e os trechos recuperados. O Trokim não fabrica um comparativo sem evidências.',
                        style: TextStyle(
                            fontSize: 12,
                            height: 1.4,
                            color: context.colors.ink),
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
                      return Padding(
                        padding: EdgeInsets.symmetric(vertical: 12),
                        child: Row(
                          children: [
                            SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(
                                  strokeWidth: 2.4,
                                  color: context.colors.accent),
                            ),
                            SizedBox(width: 12),
                            Text('Consultando fontes oficiais...',
                                style: TextStyle(color: context.colors.muted)),
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
              margin: const EdgeInsets.fromLTRB(16, 4, 16, 6),
              padding: const EdgeInsets.fromLTRB(18, 4, 6, 4),
              decoration: BoxDecoration(
                color: context.colors.surface,
                borderRadius: BorderRadius.circular(26),
                border: Border.all(color: context.colors.line),
                boxShadow: AppTheme.softShadow(context),
              ),
              child: SafeArea(
                top: false,
                bottom: false,
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _textController,
                        enabled: !_chat.isLoading,
                        maxLength: 1000,
                        buildCounter: (_,
                                {required currentLength,
                                required isFocused,
                                maxLength}) =>
                            null,
                        minLines: 1,
                        maxLines: 3,
                        textInputAction: TextInputAction.send,
                        decoration: const InputDecoration(
                          hintText: 'Pergunte sobre orçamento ou reserva…',
                          border: InputBorder.none,
                        ),
                        onSubmitted: (_) => _sendMessage(),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.only(bottom: 2),
                      child: IconButton.filled(
                        tooltip: 'Enviar',
                        icon: const Icon(Icons.send, size: 20),
                        style: IconButton.styleFrom(
                          backgroundColor: context.colors.accent,
                          disabledBackgroundColor: context.colors.line,
                          foregroundColor: Colors.white,
                        ),
                        onPressed: _chat.isLoading ? null : _sendMessage,
                      ),
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
        ? AppTheme.emerald
        : message.isError
            ? AppTheme.negative.withValues(alpha: 0.14)
            : message.isAbstained
                ? context.colors.line
                : context.colors.surface;
    final radius = BorderRadius.only(
      topLeft: const Radius.circular(20),
      topRight: const Radius.circular(20),
      bottomLeft: Radius.circular(message.isUser ? 20 : 6),
      bottomRight: Radius.circular(message.isUser ? 6 : 20),
    );
    return Reveal(
      step: Duration.zero,
      offset: 10,
      child: Align(
        alignment:
            message.isUser ? Alignment.centerRight : Alignment.centerLeft,
        child: Container(
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.all(14),
          constraints: BoxConstraints(maxWidth: maxWidth),
          decoration: BoxDecoration(
            color: color,
            borderRadius: radius,
            border:
                message.isUser ? null : Border.all(color: context.colors.line),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (message.isAbstained || message.isError) ...[
                Icon(
                  message.isError
                      ? Icons.error_outline
                      : Icons.warning_amber_rounded,
                  color: message.isError
                      ? AppTheme.negative
                      : context.colors.muted,
                  semanticLabel: message.isError
                      ? 'Erro de conexão'
                      : 'Sem evidências suficientes',
                ),
                const SizedBox(height: 8),
              ],
              Text(
                message.text,
                style: TextStyle(
                  color: message.isUser ? Colors.white : context.colors.ink,
                  fontSize: 14.5,
                  height: 1.45,
                ),
              ),
              if (message.isAbstained)
                Padding(
                  padding: const EdgeInsets.only(top: 10),
                  child: Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: AppTheme.gold.withValues(alpha: 0.16),
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
    final grounded = message.status == 'grounded';
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: context.colors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: context.colors.line),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Comparativo de transparência',
            style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12)),
        const SizedBox(height: 8),
        _AuditRow(
          icon: grounded ? Icons.verified : Icons.warning_amber_rounded,
          color: grounded ? AppTheme.positive : context.colors.muted,
          title: grounded ? 'Com RAG' : 'Com RAG: abstenção ética',
          body: grounded
              ? 'Resposta vinculada às fontes oficiais abaixo.'
              : 'O sistema não encontrou evidências suficientes para orientar.',
        ),
        const SizedBox(height: 7),
        _AuditRow(
          icon: Icons.link_off,
          color: context.colors.accent,
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
