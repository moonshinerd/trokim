import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/app_motion.dart';
import '../../../core/widgets/trokim_logo.dart';
import '../domain/conversation.dart';
import 'chat_controller.dart';

/// Histórico de conversas: abrir, renomear e apagar.
class HistoryScreen extends StatelessWidget {
  const HistoryScreen({super.key, required this.chat});

  final ChatController chat;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Conversas'),
        actions: [
          IconButton(
            tooltip: 'Nova conversa',
            icon: const Icon(Icons.add_comment_outlined),
            onPressed: () {
              chat.startNew();
              Navigator.of(context).pop();
            },
          ),
        ],
      ),
      body: ListenableBuilder(
        listenable: chat,
        builder: (context, _) {
          final items = chat.conversations;
          if (items.isEmpty) return const _EmptyState();
          return ListView.builder(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
            itemCount: items.length,
            itemBuilder: (context, i) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Reveal(
                index: i.clamp(0, 8),
                step: const Duration(milliseconds: 40),
                child: _ConversationTile(
                  conversation: items[i],
                  selected: items[i].id == chat.current?.id,
                  onOpen: () {
                    chat.open(items[i].id);
                    Navigator.of(context).pop();
                  },
                  onRename: () => _rename(context, items[i]),
                  onDelete: () => _confirmDelete(context, items[i]),
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Future<void> _rename(BuildContext context, Conversation c) async {
    final title = await showDialog<String>(
      context: context,
      builder: (context) => _RenameDialog(initial: c.title),
    );
    if (title != null) await chat.rename(c.id, title);
  }

  Future<void> _confirmDelete(BuildContext context, Conversation c) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Apagar conversa?'),
        content: Text(
            '"${c.title}" será apagada deste aparelho. Isso não pode ser desfeito.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppTheme.negative),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Apagar'),
          ),
        ],
      ),
    );
    if (ok == true) await chat.delete(c.id);
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const TrokimMark(size: 72),
            const SizedBox(height: 16),
            const Text('Nenhuma conversa ainda',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
            const SizedBox(height: 6),
            Text(
              'Suas conversas com o assistente aparecem aqui, guardadas só neste aparelho.',
              textAlign: TextAlign.center,
              style: TextStyle(color: context.colors.muted, height: 1.4),
            ),
          ]),
        ),
      );
}

class _ConversationTile extends StatelessWidget {
  const _ConversationTile({
    required this.conversation,
    required this.selected,
    required this.onOpen,
    required this.onRename,
    required this.onDelete,
  });

  final Conversation conversation;
  final bool selected;
  final VoidCallback onOpen;
  final VoidCallback onRename;
  final VoidCallback onDelete;

  static String when(DateTime t, [DateTime? now]) {
    final n = now ?? DateTime.now();
    final day = DateTime(t.year, t.month, t.day);
    final today = DateTime(n.year, n.month, n.day);
    final diff = today.difference(day).inDays;
    if (diff == 0) return 'Hoje, ${DateFormat('HH:mm').format(t)}';
    if (diff == 1) return 'Ontem';
    return DateFormat('dd/MM').format(t);
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final generating = conversation.titleState == TitleState.generating;
    final provisional =
        conversation.titleState == TitleState.placeholder || generating;
    return Material(
      color: selected ? c.tint : c.surface,
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppTheme.radius),
        side: BorderSide(color: selected ? AppTheme.gold : c.line),
      ),
      child: InkWell(
        onTap: onOpen,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 4, 12),
          child: Row(children: [
            Expanded(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    AnimatedSwitcher(
                      duration: Motion.base,
                      child: Text(
                        conversation.title,
                        key: ValueKey(conversation.title),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontWeight: FontWeight.w800,
                          fontSize: 15,
                          fontStyle:
                              provisional ? FontStyle.italic : FontStyle.normal,
                          color: provisional ? c.muted : c.ink,
                        ),
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      conversation.preview,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(color: c.muted, fontSize: 13),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      generating
                          ? '${when(conversation.updatedAt)} · gerando título…'
                          : when(conversation.updatedAt),
                      style: TextStyle(color: c.muted, fontSize: 11.5),
                    ),
                  ]),
            ),
            PopupMenuButton<String>(
              tooltip: 'Opções da conversa',
              icon: Icon(Icons.more_vert_rounded, color: c.muted),
              onSelected: (v) => v == 'rename' ? onRename() : onDelete(),
              itemBuilder: (_) => const [
                PopupMenuItem(value: 'rename', child: Text('Renomear')),
                PopupMenuItem(value: 'delete', child: Text('Apagar')),
              ],
            ),
          ]),
        ),
      ),
    );
  }
}

/// Diálogo de renomear: o próprio widget cuida do ciclo de vida do campo.
class _RenameDialog extends StatefulWidget {
  const _RenameDialog({required this.initial});
  final String initial;

  @override
  State<_RenameDialog> createState() => _RenameDialogState();
}

class _RenameDialogState extends State<_RenameDialog> {
  late final TextEditingController _controller =
      TextEditingController(text: widget.initial);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: const Text('Renomear conversa'),
        content: TextField(
          controller: _controller,
          autofocus: true,
          maxLength: 60,
          textInputAction: TextInputAction.done,
          decoration: const InputDecoration(hintText: 'Título da conversa…'),
          onSubmitted: (v) => Navigator.of(context).pop(v),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(_controller.text),
            child: const Text('Salvar'),
          ),
        ],
      );
}
