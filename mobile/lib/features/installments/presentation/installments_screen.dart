import 'package:material_ui/material_ui.dart';

import '../../../core/format.dart';
import '../../../core/theme/app_theme.dart';
import '../../finance/domain/library_models.dart';
import '../../finance/presentation/finance_controller.dart';

/// Controle dos parcelamentos dos cartões importados: o que falta pagar e a projeção por mês.
class InstallmentsScreen extends StatelessWidget {
  const InstallmentsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final data = FinanceScope.of(context).installments;
    final c = context.colors;
    final active = data.plans.where((p) => !p.finished).toList();
    final finished = data.plans.where((p) => p.finished).toList();
    return Scaffold(
      appBar: AppBar(title: const Text('Parcelamentos')),
      body: SafeArea(
        child: data.isEmpty
            ? Center(
                child: Padding(
                  padding: const EdgeInsets.all(32),
                  child: Text(
                    'Nenhum parcelamento encontrado nas faturas importadas.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: c.muted),
                  ),
                ),
              )
            : ListView(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
                children: [
                  _TotalCard(data: data),
                  if (data.projection.isNotEmpty) ...[
                    const SizedBox(height: 24),
                    Semantics(
                      header: true,
                      child: Text(
                        'Próximos meses',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Quanto já está comprometido em parcelas, sem contar compras novas.',
                      style: TextStyle(color: c.muted, fontSize: 13),
                    ),
                    const SizedBox(height: 12),
                    _Projection(months: data.projection),
                  ],
                  const SizedBox(height: 24),
                  Semantics(
                    header: true,
                    child: Text(
                      'Em andamento',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                  ),
                  const SizedBox(height: 10),
                  if (active.isEmpty)
                    Text(
                      'Nenhum parcelamento em andamento.',
                      style: TextStyle(color: c.muted),
                    ),
                  for (final plan in active) _PlanTile(plan: plan),
                  if (finished.isNotEmpty) ...[
                    const SizedBox(height: 24),
                    Semantics(
                      header: true,
                      child: Text(
                        'Quitados',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                    ),
                    const SizedBox(height: 10),
                    for (final plan in finished) _PlanTile(plan: plan),
                  ],
                ],
              ),
      ),
    );
  }
}

class _TotalCard extends StatelessWidget {
  const _TotalCard({required this.data});
  final InstallmentsData data;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Semantics(
      label:
          '${brl.format(data.totalRemaining)} ainda a pagar em '
          '${data.activeCount} parcelamentos',
      child: ExcludeSemantics(
        child: Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: c.tint,
            borderRadius: BorderRadius.circular(AppTheme.radius),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Ainda a pagar', style: TextStyle(color: c.muted)),
              const SizedBox(height: 4),
              Text(
                brl.format(data.totalRemaining),
                style: const TextStyle(
                  fontSize: 30,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                data.activeCount == 1
                    ? '1 compra parcelada em andamento'
                    : '${data.activeCount} compras parceladas em andamento',
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Projection extends StatelessWidget {
  const _Projection({required this.months});
  final List<MonthTotal> months;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final max = months
        .map((m) => m.total)
        .fold<double>(0, (a, b) => a > b ? a : b);
    return Column(
      children: [
        for (final item in months)
          Semantics(
            label: '${monthLabel(item.month)}, ${brl.format(item.total)}',
            child: ExcludeSemantics(
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  children: [
                    SizedBox(width: 70, child: Text(monthLabel(item.month))),
                    Expanded(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(6),
                        child: LinearProgressIndicator(
                          value: max <= 0 ? 0 : item.total / max,
                          minHeight: 10,
                          backgroundColor: c.line,
                          valueColor: AlwaysStoppedAnimation(c.accent),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    SizedBox(
                      width: 92,
                      child: Text(
                        brl.format(item.total),
                        textAlign: TextAlign.end,
                        style: const TextStyle(fontWeight: FontWeight.w700),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }
}

class _PlanTile extends StatelessWidget {
  const _PlanTile({required this.plan});
  final InstallmentPlan plan;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final status = plan.finished
        ? 'Quitado'
        : 'Faltam ${plan.remaining} · ${brl.format(plan.remainingAmount)} · '
              'termina em ${monthLabel(plan.endsOnMonth)}';
    return Semantics(
      label:
          '${plan.merchant}, parcela ${plan.current} de ${plan.total}, '
          '${brl.format(plan.amount)} por parcela. $status',
      child: ExcludeSemantics(
        child: Container(
          margin: const EdgeInsets.only(bottom: 10),
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
                      plan.merchant,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontWeight: FontWeight.w800,
                        fontSize: 16,
                      ),
                    ),
                  ),
                  Text(
                    '${brl.format(plan.amount)} / mês',
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ],
              ),
              if (plan.accountLabel.isNotEmpty)
                Text(plan.accountLabel, style: TextStyle(color: c.muted)),
              const SizedBox(height: 10),
              ClipRRect(
                borderRadius: BorderRadius.circular(6),
                child: LinearProgressIndicator(
                  value: plan.progress,
                  minHeight: 8,
                  backgroundColor: c.line,
                  valueColor: AlwaysStoppedAnimation(c.accent),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Parcela ${plan.current} de ${plan.total}',
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
              Text(status, style: TextStyle(color: c.muted, fontSize: 13)),
            ],
          ),
        ),
      ),
    );
  }
}
