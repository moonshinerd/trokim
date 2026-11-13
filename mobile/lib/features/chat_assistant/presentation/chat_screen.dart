import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/app_motion.dart';
import '../../../core/widgets/trokim_logo.dart';
import '../domain/answer_format.dart';
import '../domain/chat_models.dart';
import '../domain/conversation.dart';
import '../../../core/settings/settings_controller.dart';
import '../data/conversation_store.dart';
import 'chat_controller.dart';
import 'history_screen.dart';
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
    _chat =
        widget.controller ?? ChatController(store: PrefsConversationStore());
    if (widget.controller == null) _chat.init();
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

  void _openHistory() {
    Navigator.of(
      context,
    ).push(MaterialPageRoute<void>(builder: (_) => HistoryScreen(chat: _chat)));
  }

  @override
  Widget build(BuildContext context) {
    // O controlador criado aqui segue a opção de Ajustes (IA ou extrativo).
    if (widget.controller == null) {
      _chat.generative = SettingsScope.of(context).generativeChat;
    }
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            const TrokimMark(size: 30),
            const SizedBox(width: 10),
            Flexible(child: _ConversationTitle(chat: _chat)),
          ],
        ),
        actions: [
          if (_chat.hasHistory) ...[
            IconButton(
              tooltip: 'Histórico de conversas',
              icon: const Icon(Icons.history_rounded),
              onPressed: _openHistory,
            ),
            IconButton(
              tooltip: 'Nova conversa',
              icon: const Icon(Icons.add_comment_outlined),
              onPressed: _chat.startNew,
            ),
          ],
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Semantics(
                label: 'Modo de auditoria pedagógica',
                child: Tooltip(
                  message: 'Auditoria pedagógica',
                  child: Switch(
                    value: _auditMode,
                    onChanged: (value) => setState(() => _auditMode = value),
                  ),
                ),
              ),
            ],
          ),
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
                    Icon(
                      Icons.fact_check_outlined,
                      color: context.colors.accent,
                      size: 19,
                    ),
                    SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Auditoria pedagógica: respostas fundamentadas exibem as fontes e os trechos recuperados. O Trokim não fabrica um comparativo sem evidências.',
                        style: TextStyle(
                          fontSize: 12,
                          height: 1.4,
                          color: context.colors.ink,
                        ),
                      ),
                    ),
                  ],
                ),
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
                                color: context.colors.accent,
                              ),
                            ),
                            SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                'Consultando fontes e gerando resposta...',
                                style: TextStyle(color: context.colors.muted),
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
                        buildCounter: (
                          _, {
                          required currentLength,
                          required isFocused,
                          maxLength,
                        }) => null,
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

class _MessageBubble extends StatefulWidget {
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
  State<_MessageBubble> createState() => _MessageBubbleState();
}

class _MessageBubbleState extends State<_MessageBubble> {
  // O State é reaproveitado quando a mensagem daquela posição muda (ex.: o erro
  // vira resposta no "tentar novamente"), então as chaves acompanham a mensagem
  // atual em vez de serem criadas uma única vez.
  final List<GlobalKey<EvidenceCardState>> _cardKeys = [];

  void _syncCardKeys() {
    final n = widget.message.evidences.length;
    while (_cardKeys.length < n) {
      _cardKeys.add(GlobalKey<EvidenceCardState>());
    }
    if (_cardKeys.length > n) _cardKeys.removeRange(n, _cardKeys.length);
  }

  /// Leva ao cartão da fonte [number] (1, 2…): abre, rola e destaca.
  void _goToSource(int number) {
    if (number < 1 || number > _cardKeys.length) return;
    _cardKeys[number - 1].currentState?.reveal();
  }

  ChatMessage get message => widget.message;
  double get maxWidth => widget.maxWidth;
  VoidCallback? get onRetry => widget.onRetry;
  bool get auditMode => widget.auditMode;
  ValueChanged<String>? get onQuickQuestion => widget.onQuickQuestion;

  @override
  Widget build(BuildContext context) {
    _syncCardKeys();
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
        alignment: message.isUser
            ? Alignment.centerRight
            : Alignment.centerLeft,
        child: Container(
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.all(14),
          constraints: BoxConstraints(maxWidth: maxWidth),
          decoration: BoxDecoration(
            color: color,
            borderRadius: radius,
            border: message.isUser
                ? null
                : Border.all(color: context.colors.line),
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
              _MessageText(message: message, onSource: _goToSource),
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
                Wrap(
                  spacing: 4,
                  runSpacing: 0,
                  children: [
                    _QuickQuestion(
                      label: 'Reserva de emergência',
                      onPressed: () => onQuickQuestion?.call(
                        'Como começar uma reserva de emergência?',
                      ),
                    ),
                    _QuickQuestion(
                      label: 'Organizar o orçamento',
                      onPressed: () => onQuickQuestion?.call(
                        'Como organizar meu orçamento mensal?',
                      ),
                    ),
                  ],
                ),
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
                for (var i = 0; i < message.evidences.length; i++) ...[
                  const SizedBox(height: 8),
                  EvidenceCard(
                    key: _cardKeys[i],
                    evidence: message.evidences[i],
                    number: i + 1,
                  ),
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
    final grounded = message.status == AssistantStatus.grounded;
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: context.colors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: context.colors.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Comparativo de transparência',
            style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12),
          ),
          const SizedBox(height: 8),
          _AuditRow(
            icon: grounded ? Icons.verified : Icons.warning_amber_rounded,
            color: grounded ? AppTheme.positive : context.colors.muted,
            title: grounded ? 'Com RAG' : 'Com RAG: abstenção ética',
            body: grounded ? 'Resposta vinculada às fontes oficiais abaixo.' : 'O sistema não encontrou evidências suficientes para orientar.',
          ),
          const SizedBox(height: 7),
          _AuditRow(
            icon: Icons.link_off,
            color: context.colors.accent,
            title: 'Sem lastro verificável',
            body: 'Nenhuma resposta alternativa é apresentada: sem fontes, um palpite poderia induzir a uma decisão financeira inadequada.',
          ),
        ],
      ),
    );
  }
}

class _AuditRow extends StatelessWidget {
  const _AuditRow({
    required this.icon,
    required this.color,
    required this.title,
    required this.body,
  });
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
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: TextStyle(
                fontWeight: FontWeight.w600,
                color: color,
                fontSize: 11,
              ),
            ),
            Text(body, style: const TextStyle(fontSize: 11, height: 1.35)),
          ],
        ),
      ),
    ],
  );
}

/// Título da conversa na barra: "Assistente" numa conversa nova; depois, o
/// título provisório (a primeira pergunta) que troca suavemente pelo do LLM.
class _ConversationTitle extends StatelessWidget {
  const _ConversationTitle({required this.chat});
  final ChatController chat;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: chat,
      builder: (context, _) {
        final conv = chat.current;
        final generating = conv?.titleState == TitleState.generating;
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Flexible(
              child: AnimatedSwitcher(
                duration: Motion.base,
                switchInCurve: Motion.emphasized,
                transitionBuilder: (child, anim) => FadeTransition(
                  opacity: anim,
                  child: SlideTransition(
                    position: Tween<Offset>(
                      begin: const Offset(0, 0.25),
                      end: Offset.zero,
                    ).animate(anim),
                    child: child,
                  ),
                ),
                child: Text(
                  conv?.title ?? 'Assistente',
                  key: ValueKey(conv?.title ?? 'Assistente'),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ),
            if (generating) ...[
              const SizedBox(width: 8),
              Semantics(label: 'Gerando título', child: const _TypingDots()),
            ],
          ],
        );
      },
    );
  }
}

/// Três pontinhos pulsando: "gerando título".
class _TypingDots extends StatefulWidget {
  const _TypingDots();

  @override
  State<_TypingDots> createState() => _TypingDotsState();
}

class _TypingDotsState extends State<_TypingDots>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1000),
  )..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final color = context.colors.muted;
    return AnimatedBuilder(
      animation: _c,
      builder: (_, __) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          for (var i = 0; i < 3; i++)
            Container(
              width: 5,
              height: 5,
              margin: const EdgeInsets.symmetric(horizontal: 1.5),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: color.withValues(
                  alpha: 0.25 + 0.75 * (((_c.value * 3) - i) % 3 < 1 ? 1 : 0.0),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// Texto da mensagem. As respostas do assistente saem sem o bloco de fontes e
/// sem URLs soltas; cada marcador [n] vira o nome da fonte, como um link no
/// próprio texto, que leva ao cartão da fonte logo abaixo.
class _MessageText extends StatefulWidget {
  const _MessageText({required this.message, required this.onSource});
  final ChatMessage message;
  final ValueChanged<int> onSource;

  @override
  State<_MessageText> createState() => _MessageTextState();
}

class _MessageTextState extends State<_MessageText> {
  final List<TapGestureRecognizer> _taps = [];

  void _disposeTaps() {
    for (final t in _taps) {
      t.dispose();
    }
    _taps.clear();
  }

  @override
  void dispose() {
    _disposeTaps();
    super.dispose();
  }

  /// "BCB · Caderno de Educação Fin…": instituição + título, com limite.
  static String sourceLabel(Evidence e, {int max = 30}) {
    final name = e.sourceName.toLowerCase();
    final inst = name.contains('banco central') || name.contains('bcb')
        ? 'BCB'
        : name.contains('cvm')
        ? 'CVM'
        : name.contains('cfpb')
        ? 'CFPB'
        : e.sourceName;
    final full = '$inst · ${e.documentTitle}';
    return full.length <= max
        ? full
        : '${full.substring(0, max - 1).trimRight()}…';
  }

  @override
  Widget build(BuildContext context) {
    final message = widget.message;
    final style = TextStyle(
      color: message.isUser ? Colors.white : context.colors.ink,
      fontSize: 14.5,
      height: 1.45,
    );
    if (message.isUser || message.isError || message.isAbstained) {
      return Text(message.text, style: style);
    }
    _disposeTaps();
    final link = context.colors.accent;
    final cleaned = AnswerFormat.clean(message.text);
    return Text.rich(
      TextSpan(
        style: style,
        children: AnswerFormat.spans(
          cleaned,
          style,
          citationColor: link,
          citation: (n) {
            if (n < 1 || n > message.evidences.length) {
              return TextSpan(text: '[$n]');
            }
            final tap = TapGestureRecognizer()
              ..onTap = () => widget.onSource(n);
            _taps.add(tap);
            return TextSpan(
              text: sourceLabel(message.evidences[n - 1]),
              recognizer: tap,
              semanticsLabel:
                  'Ver fonte: ${message.evidences[n - 1].documentTitle}',
              style: TextStyle(
                color: link,
                fontWeight: FontWeight.w700,
                decoration: TextDecoration.underline,
                decorationColor: link.withValues(alpha: 0.5),
              ),
            );
          },
        ),
      ),
    );
  }
}
