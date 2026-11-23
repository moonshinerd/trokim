import 'package:material_ui/material_ui.dart';

import '../../../core/format.dart';
import '../../../core/theme/app_theme.dart';
import '../../finance/presentation/finance_controller.dart';
import '../domain/categories.dart';
import '../domain/ledger_entry.dart';

/// Revisão das categorias dos gastos importados.
///
/// O app nunca decide sozinho: a categoria vem das regras locais da API e o usuário corrige.
/// Por padrão, a correção vale para todos os lançamentos do mesmo estabelecimento e para os
/// próximos arquivos (a API guarda a regra).
class CategoryReviewScreen extends StatefulWidget {
  const CategoryReviewScreen({super.key, this.initialFilter = 'outros'});

  /// Categoria mostrada ao abrir; `null` mostra todos os gastos.
  final String? initialFilter;

  @override
  State<CategoryReviewScreen> createState() => _CategoryReviewScreenState();
}

class _CategoryReviewScreenState extends State<CategoryReviewScreen> {
  late String? _filter = widget.initialFilter;
  List<LedgerEntry>? _entries;
  bool _failed = false;
  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_started) {
      _started = true;
      _reload();
    }
  }

  Future<void> _reload() async {
    final finance = FinanceScope.of(context);
    try {
      final entries = await finance.fetchEntries();
      if (!mounted) return;
      setState(() {
        _entries = entries.where((e) => e.isEditableExpense).toList()
          ..sort((a, b) => b.date.compareTo(a.date));
        _failed = false;
      });
    } on Object {
      if (!mounted) return;
      setState(() => _failed = true);
    }
  }

  Future<void> _edit(LedgerEntry entry) async {
    final choice = await showModalBottomSheet<_Choice>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => _CategorySheet(entry: entry),
    );
    if (choice == null || !mounted) return;
    final finance = FinanceScope.of(context);
    final messenger = ScaffoldMessenger.of(context);
    try {
      final change = await finance.setCategory(
        entry,
        choice.category,
        applyToMerchant: choice.applyToMerchant,
      );
      final name = categoryInfo(choice.category).name;
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(
          SnackBar(
            content: Text(
              change.updated > 1
                  ? '${change.updated} lançamentos agora em $name.'
                  : 'Lançamento agora em $name.',
            ),
          ),
        );
      await _reload();
    } on Object {
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(
          const SnackBar(
            content: Text('Não foi possível salvar. Tente novamente.'),
          ),
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final entries = _entries;
    final visible = entries == null
        ? const <LedgerEntry>[]
        : entries
              .where((e) => _filter == null || e.category == _filter)
              .toList();
    final uncategorized = entries?.where((e) => e.category == 'outros').length;
    return Scaffold(
      appBar: AppBar(title: const Text('Categorias dos gastos')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
          children: [
            Text(
              'Toque num gasto para escolher a categoria. O Trokim lembra da '
              'escolha para o mesmo estabelecimento nos próximos arquivos.',
              style: TextStyle(color: c.muted, height: 1.4),
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                ChoiceChip(
                  label: Text(
                    uncategorized == null
                        ? 'Sem categoria'
                        : 'Sem categoria ($uncategorized)',
                  ),
                  selected: _filter == 'outros',
                  onSelected: (_) => setState(() => _filter = 'outros'),
                ),
                ChoiceChip(
                  label: const Text('Todos os gastos'),
                  selected: _filter == null,
                  onSelected: (_) => setState(() => _filter = null),
                ),
                if (_filter != null && _filter != 'outros')
                  ChoiceChip(
                    label: Text(categoryInfo(_filter!).name),
                    selected: true,
                    onSelected: (_) {},
                  ),
              ],
            ),
            const SizedBox(height: 16),
            if (_failed)
              _Message(
                text:
                    'Não foi possível carregar os lançamentos. Confira a API '
                    'em Ajustes.',
                action: TextButton(
                  onPressed: _reload,
                  child: const Text('Tentar de novo'),
                ),
              )
            else if (entries == null)
              const Padding(
                padding: EdgeInsets.all(32),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (visible.isEmpty)
              _Message(
                text: _filter == 'outros'
                    ? 'Tudo categorizado. Nenhum gasto em "Outros".'
                    : 'Nenhum gasto aqui.',
              )
            else
              for (final entry in visible)
                _EntryTile(entry: entry, onTap: () => _edit(entry)),
          ],
        ),
      ),
    );
  }
}

class _Message extends StatelessWidget {
  const _Message({required this.text, this.action});

  final String text;
  final Widget? action;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 24),
    child: Column(
      children: [
        Text(
          text,
          textAlign: TextAlign.center,
          style: TextStyle(color: context.colors.muted),
        ),
        ?action,
      ],
    ),
  );
}

class _EntryTile extends StatelessWidget {
  const _EntryTile({required this.entry, required this.onTap});

  final LedgerEntry entry;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final info = categoryInfo(entry.category);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Material(
        color: c.surface,
        borderRadius: BorderRadius.circular(AppTheme.radius),
        child: InkWell(
          borderRadius: BorderRadius.circular(AppTheme.radius),
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(AppTheme.radius),
              border: Border.all(color: c.line),
            ),
            child: Row(
              children: [
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: info.color.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(info.icon, color: info.color, size: 20),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        entry.title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontWeight: FontWeight.w700),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        '${shortDate(entry.date)} · ${info.name}',
                        style: TextStyle(color: c.muted, fontSize: 13),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  brl.format(entry.amount),
                  style: const TextStyle(
                    fontWeight: FontWeight.w800,
                    fontFeatures: [FontFeature.tabularFigures()],
                  ),
                ),
                const SizedBox(width: 4),
                Icon(Icons.chevron_right_rounded, color: c.muted),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Choice {
  const _Choice(this.category, this.applyToMerchant);

  final String category;
  final bool applyToMerchant;
}

class _CategorySheet extends StatefulWidget {
  const _CategorySheet({required this.entry});

  final LedgerEntry entry;

  @override
  State<_CategorySheet> createState() => _CategorySheetState();
}

class _CategorySheetState extends State<_CategorySheet> {
  late String _selected = widget.entry.category;
  bool _applyToMerchant = true;

  bool get _hasMerchant => (widget.entry.merchant?.trim() ?? '').isNotEmpty;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final entry = widget.entry;
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              entry.title,
              style: Theme.of(context).textTheme.titleLarge,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            Text(
              '${fullDate(entry.date)} · ${brl.format(entry.amount)}',
              style: TextStyle(color: c.muted),
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final item in expenseCategories)
                  ChoiceChip(
                    avatar: Icon(item.icon, size: 18, color: item.color),
                    label: Text(item.name),
                    selected: _selected == item.key,
                    onSelected: (_) => setState(() => _selected = item.key),
                  ),
              ],
            ),
            if (_hasMerchant) ...[
              const SizedBox(height: 12),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                value: _applyToMerchant,
                onChanged: (value) => setState(() => _applyToMerchant = value),
                title: Text('Usar para tudo de ${entry.merchant!.trim()}'),
                subtitle: const Text(
                  'Vale para os lançamentos já importados e para os próximos '
                  'arquivos.',
                ),
              ),
            ],
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _selected == entry.category && !_applyToMerchant
                    ? null
                    : () => Navigator.of(context).pop(
                        _Choice(_selected, _hasMerchant && _applyToMerchant),
                      ),
                child: const Text('Salvar'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
