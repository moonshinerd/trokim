import 'package:flutter/gestures.dart';
import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/format.dart';
import '../../../core/widgets/app_motion.dart';
import '../../../core/widgets/trokim_logo.dart';
import '../../finance/presentation/finance_controller.dart';
import '../../import_guide/presentation/import_flow_screen.dart';
import '../../transactions/presentation/transactions_screen.dart';
import '../domain/answer_format.dart';
import '../domain/chat_models.dart';
import '../domain/conversation.dart';
import '../../../core/settings/settings_controller.dart';
import '../data/conversation_store.dart';
import 'chat_controller.dart';
import 'history_screen.dart';
import 'evidence_card.dart';

const _monthNames = [
  'janeiro',
  'fevereiro',
  'março',
  'abril',
  'maio',
  'junho',
  'julho',
  'agosto',
  'setembro',
  'outubro',
  'novembro',
  'dezembro',
];

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key, this.controller, this.importPicker});

  final ChatController? controller;

  /// Troca o seletor de arquivos do fluxo de importação (testes).
  final StatementPicker? importPicker;

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  late ChatController _chat;
  bool _auditMode = false;
  String _scopeKey = 'todas';
  String _periodKey = 'todos';

  @override
  void initState() {
    super.initState();
    final settings = SettingsScope.read(context);
    _chat =
        widget.controller ??
        ChatController(
          store: PrefsConversationStore(),
          baseUrlProvider: settings == null ? null : () => settings.apiBaseUrl,
        );
    _chat.hasImportedData = () {
      final finance = FinanceScope.read(context);
      if (finance == null) return true;
      return finance.files.isNotEmpty || finance.status != FinanceStatus.ready;
    };
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

  void _applyFilters() {
    String? accountId;
    String? owner;
    if (_scopeKey.startsWith('acc:')) {
      accountId = _scopeKey.substring(4);
    } else if (_scopeKey != 'todas') {
      owner = _scopeKey;
    }
    String? period;
    if (_periodKey.startsWith('mes:')) {
      period = _periodKey.substring(4);
    } else if (_periodKey != 'todos') {
      period = _periodKey;
    }
    _chat.filters = ChatFilters(
      accountId: accountId,
      owner: owner,
      period: period,
    );
  }

  List<(String, String)> _periodOptions(FinanceController finance) {
    final months = <String>{};
    var hasCard = false;
    for (final statement in finance.statements.statements) {
      if (statement.isCard) hasCard = true;
      final start = statement.periodStart;
      final end = statement.periodEnd;
      if (start == null) continue;
      var year = start.year;
      var month = start.month;
      final lastYear = end?.year ?? year;
      final lastMonth = end?.month ?? month;
      while (year < lastYear || (year == lastYear && month <= lastMonth)) {
        months.add('$year-${month.toString().padLeft(2, '0')}');
        month++;
        if (month > 12) {
          month = 1;
          year++;
        }
      }
    }
    final sorted = months.toList()..sort((a, b) => b.compareTo(a));
    return [
      ('todos', 'Todo o período'),
      for (final month in sorted) ('mes:$month', monthLabel(month)),
      if (hasCard) ('fatura aberta', 'Fatura aberta'),
      if (hasCard) ('fatura fechada', 'Fatura fechada'),
    ];
  }

  List<(String, String)> _suggestions(FinanceController finance) {
    final out = <(String, String)>[];
    if (finance.installments.activeCount > 0) {
      out.add(('Parcelas em aberto', 'Quanto falta das parcelas?'));
    }
    final statements = finance.statements.statements;
    if (statements.any((s) => s.isCard && s.status.isIncomplete)) {
      out.add(('Fatura aberta', 'Qual o total da fatura aberta?'));
    }
    final latest = statements.where((s) => s.periodEnd != null).fold<DateTime?>(
      null,
      (max, s) {
        final end = s.periodEnd!;
        return max == null || end.isAfter(max) ? end : max;
      },
    );
    if (latest != null) {
      final name = _monthNames[latest.month - 1];
      out.add((
        'Gastos de ${monthLabel('${latest.year}-${latest.month.toString().padLeft(2, '0')}')}',
        'Quanto gastei em $name de ${latest.year}?',
      ));
    }
    if (out.isEmpty && finance.files.isNotEmpty) {
      out.add(('Gastos do mês', 'Quanto gastei este mês?'));
    }
    return out;
  }

  void _openImport() {
    final tutorial = SettingsScope.maybeOf(context)?.showImportTutorial ?? true;
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ImportFlowScreen(
          pickFile: widget.importPicker,
          startAtPicker: !tutorial,
        ),
      ),
    );
  }

  void _openEntries() {
    Navigator.of(
      context,
    ).push(MaterialPageRoute<void>(builder: (_) => const TransactionsScreen()));
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
      _chat.multiAgent = SettingsScope.of(context).multiAgent;
    }
    final finance = context
        .dependOnInheritedWidgetOfExactType<FinanceScope>()
        ?.notifier;
    final hasData = finance != null && finance.files.isNotEmpty;
    final periodOptions = hasData
        ? _periodOptions(finance)
        : const <(String, String)>[];
    final scopeOptions = hasData
        ? <(String, String)>[
            ('todas', 'Tudo'),
            ('pessoal', 'Pessoal'),
            ('empresa', 'Empresas'),
            for (final account in finance.accounts)
              ('acc:${account.id}', account.displayLabel),
          ]
        : const <(String, String)>[];
    final suggestions = hasData && _chat.messages.length <= 1
        ? _suggestions(finance)
        : const <(String, String)>[];
    if (scopeOptions.every((option) => option.$1 != _scopeKey)) {
      _scopeKey = 'todas';
    }
    if (periodOptions.every((option) => option.$1 != _periodKey)) {
      _periodKey = 'todos';
    }
    _applyFilters();
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
                    const SizedBox(width: 8),
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
                        padding: const EdgeInsets.symmetric(vertical: 12),
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
                            const SizedBox(width: 12),
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
                      onShowTrace: message.agentTrace == null
                          ? null
                          : () => _showAgentTrace(message.agentTrace!),
                      onQuickQuestion: (question) {
                        _textController.text = question;
                        _textController.selection = TextSelection.collapsed(
                          offset: question.length,
                        );
                        _sendMessage();
                      },
                      onImport: _openImport,
                      onOpenEntries: _openEntries,
                    );
                  },
                ),
              ),
            ),
            if (_chat.multiAgent && scopeOptions.length > 1)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 2, 16, 0),
                child: Row(
                  children: [
                    Expanded(
                      child: _FilterPicker(
                        key: const ValueKey('chat-scope-filter'),
                        tooltip: 'Conta ou dono',
                        value: _scopeKey,
                        options: scopeOptions,
                        onChanged: (value) => setState(() => _scopeKey = value),
                      ),
                    ),
                    if (periodOptions.length > 1) ...[
                      const SizedBox(width: 8),
                      Expanded(
                        child: _FilterPicker(
                          key: const ValueKey('chat-period-filter'),
                          tooltip: 'Período',
                          value: _periodKey,
                          options: periodOptions,
                          onChanged: (value) =>
                              setState(() => _periodKey = value),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            if (suggestions.isNotEmpty && !_chat.isLoading)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 6, 16, 0),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: Wrap(
                    spacing: 6,
                    runSpacing: 4,
                    children: [
                      for (final (label, question) in suggestions)
                        _QuickQuestion(
                          label: label,
                          onPressed: () {
                            _textController.text = question;
                            _textController.selection = TextSelection.collapsed(
                              offset: question.length,
                            );
                            _sendMessage();
                          },
                        ),
                    ],
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

  void _showAgentTrace(Map<String, dynamic> trace) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      sheetAnimationStyle: Motion.reduced(context)
          ? AnimationStyle.noAnimation
          : null,
      builder: (context) => _AgentTraceSheet(trace: trace),
    );
  }
}

class _MessageBubble extends StatefulWidget {
  const _MessageBubble({
    required this.message,
    required this.maxWidth,
    this.onRetry,
    required this.auditMode,
    this.onShowTrace,
    this.onQuickQuestion,
    this.onImport,
    this.onOpenEntries,
  });

  final ChatMessage message;
  final double maxWidth;
  final VoidCallback? onRetry;
  final bool auditMode;
  final VoidCallback? onShowTrace;
  final ValueChanged<String>? onQuickQuestion;
  final VoidCallback? onImport;
  final VoidCallback? onOpenEntries;

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
  VoidCallback? get onShowTrace => widget.onShowTrace;
  ValueChanged<String>? get onQuickQuestion => widget.onQuickQuestion;
  VoidCallback? get onImport => widget.onImport;
  VoidCallback? get onOpenEntries => widget.onOpenEntries;

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
              if (message.isImportGuide && onImport != null)
                Padding(
                  padding: const EdgeInsets.only(top: 10),
                  child: FilledButton.icon(
                    onPressed: onImport,
                    icon: const Icon(Icons.file_upload_outlined, size: 18),
                    label: const Text('Importar extrato'),
                  ),
                ),
              if (!message.isUser && !message.isError)
                _CalculationCards(
                  trace: message.agentTrace,
                  onOpenEntries: onOpenEntries,
                ),
              if (onShowTrace != null)
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    onPressed: onShowTrace,
                    icon: const Icon(Icons.account_tree_outlined, size: 17),
                    label: const Text('Como cheguei a essa resposta'),
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

class _FilterPicker extends StatelessWidget {
  const _FilterPicker({
    super.key,
    required this.tooltip,
    required this.value,
    required this.options,
    required this.onChanged,
  });

  final String tooltip;
  final String value;
  final List<(String, String)> options;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10),
        decoration: BoxDecoration(
          color: context.colors.surface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: context.colors.line),
        ),
        child: DropdownButtonHideUnderline(
          child: DropdownButton<String>(
            value: value,
            isExpanded: true,
            isDense: true,
            iconSize: 18,
            style: TextStyle(
              fontSize: 12.5,
              fontWeight: FontWeight.w600,
              color: context.colors.ink,
            ),
            items: [
              for (final (key, label) in options)
                DropdownMenuItem<String>(
                  value: key,
                  child: Text(
                    label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
            ],
            onChanged: (next) {
              if (next != null) onChanged(next);
            },
          ),
        ),
      ),
    );
  }
}

class _CalculationCards extends StatelessWidget {
  const _CalculationCards({required this.trace, required this.onOpenEntries});

  final Map<String, dynamic>? trace;
  final VoidCallback? onOpenEntries;

  @override
  Widget build(BuildContext context) {
    final calculations = (trace?['calculations'] as List? ?? const [])
        .whereType<Map>()
        .toList();
    if (calculations.isEmpty) return const SizedBox.shrink();
    final c = context.colors;
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: c.tint,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: c.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.calculate_outlined, size: 16, color: c.accent),
              const SizedBox(width: 6),
              Text(
                'Números calculados',
                style: TextStyle(
                  fontWeight: FontWeight.w800,
                  fontSize: 12,
                  color: c.ink,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          for (final item in calculations)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 3),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      '${item['label']}',
                      style: TextStyle(fontSize: 12.5, color: c.ink),
                    ),
                  ),
                  Text(
                    _calculationText(item),
                    style: TextStyle(
                      fontWeight: FontWeight.w800,
                      fontSize: 13,
                      color: c.ink,
                    ),
                  ),
                ],
              ),
            ),
          if (onOpenEntries != null)
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: onOpenEntries,
                icon: const Icon(Icons.receipt_long_outlined, size: 16),
                label: const Text('Ver lançamentos'),
              ),
            ),
        ],
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

class _AgentTraceSheet extends StatelessWidget {
  const _AgentTraceSheet({required this.trace});
  final Map<String, dynamic> trace;

  @override
  Widget build(BuildContext context) {
    final steps = (trace['steps'] as List? ?? const []).whereType<Map>();
    final calculations = (trace['calculations'] as List? ?? const [])
        .whereType<Map>();
    final issues = (trace['validation_issues'] as List? ?? const [])
        .whereType<Map>();
    final evidences = (trace['evidences'] as List? ?? const [])
        .whereType<Map>();
    final status = trace['status'];
    final c = context.colors;
    String agentName(Object? key) => switch (key) {
      'research' => 'Pesquisa',
      'analysis' => 'Análise',
      'communication' => 'Comunicação',
      'validation' => 'Validação',
      _ => 'Etapa',
    };
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Como cheguei a essa resposta',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),
            if (status == 'abstained' || status == 'rejected')
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: c.tint,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  status == 'abstained'
                      ? 'Não encontrei informações suficientes para responder com segurança.'
                      : 'A resposta passou por uma checagem de segurança e não foi aprovada.',
                  style: TextStyle(color: c.ink),
                ),
              ),
            for (final step in steps)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Icon(
                  switch (step['status']) {
                    'ok' => Icons.check_circle_outline,
                    'abstained' => Icons.info_outline,
                    'skipped' => Icons.remove_circle_outline,
                    _ => Icons.error_outline,
                  },
                  color: step['status'] == 'ok' ? c.ink : c.muted,
                  semanticLabel: switch (step['status']) {
                    'ok' => 'Etapa concluída',
                    'abstained' => 'Etapa sem informações suficientes',
                    'skipped' => 'Etapa não necessária',
                    _ => 'Etapa com falha',
                  },
                ),
                title: Text(agentName(step['agent'])),
                subtitle: Text('${step['summary']}\n${step['duration_ms']} ms'),
              ),
            if (calculations.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('Cálculos', style: Theme.of(context).textTheme.titleMedium),
              for (final item in calculations) ...[
                ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  title: Text('${item['label']}'),
                  subtitle: Text(_calculationText(item)),
                ),
              ],
            ],
            if (evidences.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('Fontes', style: Theme.of(context).textTheme.titleMedium),
              for (final item in evidences)
                ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.menu_book_outlined),
                  title: Text('${item['document_title']}'),
                  subtitle: Text('${item['source_name']}'),
                ),
            ],
            for (final issue in issues)
              ListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                leading: Icon(
                  issue['severity'] == 'blocker'
                      ? Icons.block
                      : Icons.warning_amber_outlined,
                  semanticLabel: issue['severity'] == 'blocker'
                      ? 'Problema que impediu a resposta'
                      : 'Aviso',
                ),
                title: Text('${issue['message']}'),
              ),
            Text(
              'Tempo total: ${trace['total_ms']} ms',
              style: TextStyle(color: c.muted, fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }
}

String _calculationText(Map item) {
  final unit = item['unit'];
  final value = item['value'];
  if (unit == 'BRL' && value is num) {
    final fixed = value.toStringAsFixed(2).replaceAll('.', ',');
    final parts = fixed.split(',');
    final int = parts[0].replaceAllMapped(
      RegExp(r'\B(?=(\d{3})+(?!\d))'),
      (_) => '.',
    );
    return 'R\$ $int,${parts[1]}';
  }
  return unit == null ? '$value' : '$value $unit';
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
          link: (label, url) {
            final tap = TapGestureRecognizer()
              ..onTap = () async {
                final idx = message.evidences.indexWhere(
                  (e) =>
                      e.sourceUrl == url ||
                      e.sourceName.toLowerCase() == label.toLowerCase() ||
                      e.documentTitle.toLowerCase() == label.toLowerCase(),
                );
                if (idx >= 0) {
                  widget.onSource(idx + 1);
                } else {
                  final uri = Uri.tryParse(url);
                  if (uri != null && await canLaunchUrl(uri)) {
                    await launchUrl(uri, mode: LaunchMode.externalApplication);
                  }
                }
              };
            _taps.add(tap);
            return TextSpan(
              text: label,
              recognizer: tap,
              semanticsLabel: 'Ver fonte: $label',
              style: TextStyle(
                color: link,
                fontWeight: FontWeight.w700,
                decoration: TextDecoration.underline,
                decorationColor: link.withValues(alpha: 0.5),
              ),
            );
          },
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
