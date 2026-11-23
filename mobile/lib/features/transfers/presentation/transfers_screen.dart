import 'package:material_ui/material_ui.dart';

import '../../../core/format.dart';
import '../../../core/theme/app_theme.dart';
import '../../finance/domain/library_models.dart';
import '../../finance/presentation/finance_controller.dart';

/// Transferências entre as contas do usuário (e pagamentos de fatura entre bancos).
///
/// O mesmo dinheiro aparece como saída numa conta e entrada na outra. Confirmando, ele deixa
/// de contar como gasto e como receita.
class TransfersScreen extends StatelessWidget {
  const TransfersScreen({super.key});

  Future<void> _run(
    BuildContext context,
    Future<void> Function() action,
    String done,
  ) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      await action();
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(done)));
    } on Object {
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(
          const SnackBar(
            content: Text('Não foi possível concluir. Tente novamente.'),
          ),
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final finance = FinanceScope.of(context);
    final suggestions = finance.suggestions;
    final transfers = finance.transfers;
    final c = context.colors;
    return Scaffold(
      appBar: AppBar(title: const Text('Transferências entre contas')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
          children: [
            Text(
              'O mesmo dinheiro aparece como saída numa conta e entrada na '
              'outra. Ao confirmar, ele deixa de contar como gasto e como '
              'receita.',
              style: TextStyle(color: c.muted, height: 1.4),
            ),
            const SizedBox(height: 20),
            Semantics(
              header: true,
              child: Text(
                'Para confirmar',
                style: Theme.of(context).textTheme.titleLarge,
              ),
            ),
            const SizedBox(height: 10),
            if (suggestions.isEmpty)
              Text(
                'Nada para confirmar agora.',
                style: TextStyle(color: c.muted),
              ),
            for (final item in suggestions)
              _SuggestionCard(
                item: item,
                onConfirm: () => _run(
                  context,
                  () => finance.confirmTransfer(item),
                  item.isCardPayment
                      ? 'Pagamento de fatura confirmado.'
                      : 'Transferência confirmada.',
                ),
                onReject: () => _run(
                  context,
                  () => finance.rejectTransfer(item),
                  'Ok, não vou sugerir de novo.',
                ),
              ),
            const SizedBox(height: 24),
            Semantics(
              header: true,
              child: Text(
                'Já tratadas',
                style: Theme.of(context).textTheme.titleLarge,
              ),
            ),
            const SizedBox(height: 10),
            if (transfers.isEmpty)
              Text(
                'Nenhuma transferência entre suas contas ainda.',
                style: TextStyle(color: c.muted),
              ),
            for (final item in transfers)
              _HandledTile(
                item: item,
                onUndo: () => _run(
                  context,
                  () => finance.undoTransfer(item),
                  'Desfeito. O valor volta a contar nos totais.',
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _SuggestionCard extends StatelessWidget {
  const _SuggestionCard({
    required this.item,
    required this.onConfirm,
    required this.onReject,
  });

  final TransferSuggestion item;
  final VoidCallback onConfirm;
  final VoidCallback onReject;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final title = item.isCardPayment
        ? 'Pagamento de fatura de outro banco'
        : 'Transferência entre suas contas';
    final days = item.debitDate == item.creditDate
        ? shortDate(item.debitDate)
        : '${shortDate(item.debitDate)} → ${shortDate(item.creditDate)}';
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: c.surface,
        borderRadius: BorderRadius.circular(AppTheme.radius),
        border: Border.all(color: c.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
              ),
              Chip(
                visualDensity: VisualDensity.compact,
                label: Text(item.isHigh ? 'Confiança alta' : 'Confiança média'),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            brl.format(item.amount),
            style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 4),
          Text('${item.fromLabel}  →  ${item.toLabel}'),
          Text(days, style: TextStyle(color: c.muted)),
          if (item.reason.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(item.reason, style: TextStyle(color: c.muted, fontSize: 13)),
          ],
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: FilledButton(
                  onPressed: onConfirm,
                  child: const Text('Confirmar'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: OutlinedButton(
                  onPressed: onReject,
                  child: const Text('Não são'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _HandledTile extends StatelessWidget {
  const _HandledTile({required this.item, required this.onUndo});

  final OwnTransfer item;
  final VoidCallback onUndo;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final origin = item.automatic
        ? 'Reconhecida pela conta de destino'
        : 'Confirmada por você';
    final what = item.cardPayment ? 'Pagamento de fatura' : 'Transferência';
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(
        item.cardPayment
            ? Icons.credit_score_rounded
            : Icons.swap_horiz_rounded,
        color: c.accent,
      ),
      title: Text('$what · ${brl.format(item.amount)}'),
      subtitle: Text(
        '${item.fromLabel} → ${item.toLabel}\n${shortDate(item.date)} · $origin',
      ),
      isThreeLine: true,
      trailing: TextButton(onPressed: onUndo, child: const Text('Desfazer')),
    );
  }
}
