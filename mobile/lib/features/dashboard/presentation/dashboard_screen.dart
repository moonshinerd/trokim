import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/app_motion.dart';
import '../../../core/widgets/screen_header.dart';
import '../../../core/widgets/coin.dart';
import '../../finance/domain/finance_models.dart';
import '../../installments/presentation/installments_screen.dart';
import '../../transactions/presentation/statement_widgets.dart';
import '../../finance/presentation/finance_controller.dart';

final _brl = NumberFormat.currency(locale: 'pt_BR', symbol: 'R\$');

class _Category {
  const _Category(this.name, this.amount, this.icon, this.color);
  final String name;
  final double amount;
  final IconData icon;
  final Color color;
}

/// Nome, ícone e cor de cada categoria devolvida pela API.
_Category _categoryFor(String key, double amount) => switch (key) {
  'moradia' => _Category(
    'Moradia',
    amount,
    Icons.home_rounded,
    const Color(0xFF2F6FB0),
  ),
  'alimentacao' => _Category(
    'Alimentação',
    amount,
    Icons.restaurant_rounded,
    const Color(0xFFE9892F),
  ),
  'transporte' => _Category(
    'Transporte',
    amount,
    Icons.directions_car_rounded,
    AppTheme.positive,
  ),
  'lazer' => _Category(
    'Lazer e bem-estar',
    amount,
    Icons.spa_rounded,
    const Color(0xFF8B5CF6),
  ),
  'saude' => _Category(
    'Saúde',
    amount,
    Icons.favorite_rounded,
    const Color(0xFFD64F6B),
  ),
  'educacao' => _Category(
    'Educação',
    amount,
    Icons.school_rounded,
    const Color(0xFF0E8F8F),
  ),
  'servicos' => _Category(
    'Serviços',
    amount,
    Icons.receipt_rounded,
    const Color(0xFF6B7A90),
  ),
  _ => _Category(
    'Outros',
    amount,
    Icons.category_rounded,
    const Color(0xFF8A8F98),
  ),
};

/// Resumo do mês. Os números vêm de `/transactions/summary`; o app apenas
/// exibe o que o backend calculou.
class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final finance = FinanceScope.of(context);
    final summary = finance.summary;

    final Widget content;
    if (finance.status == FinanceStatus.error) {
      content = _MessageCard(
        icon: Icons.cloud_off_rounded,
        title: 'Sem conexão com a API local',
        text:
            'Confira se a API está rodando e se o endereço em Ajustes está '
            'certo.',
        action: 'Tentar novamente',
        onAction: finance.load,
      );
    } else if (summary == null) {
      content = const Padding(
        padding: EdgeInsets.symmetric(vertical: 64),
        child: Center(child: CircularProgressIndicator()),
      );
    } else if (summary.isEmpty && finance.ownerFilter == 'todas') {
      content = const _MessageCard(
        icon: Icons.inbox_rounded,
        title: 'Nenhum extrato importado ainda',
        text:
            'Importe um arquivo OFX ou uma fatura em PDF na aba Extratos para '
            'ver o seu resumo.',
      );
    } else {
      content = _SummaryContent(summary: summary);
    }

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: RefreshIndicator(
          onRefresh: finance.load,
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.only(bottom: 24),
            children: [
              const Reveal(
                child: ScreenHeader(
                  title: 'Seu mês em foco',
                  subtitle:
                      'Resumo determinístico das suas contas, no aparelho.',
                ),
              ),
              if (summary != null && finance.status != FinanceStatus.error)
                const _Filters(),
              if (summary != null && finance.status != FinanceStatus.error)
                const CoverageNotice(),
              content,
            ],
          ),
        ),
      ),
    );
  }
}

/// Filtro por dono da conta (quando há mais de um) e visão de gastos × caixa.
class _Filters extends StatelessWidget {
  const _Filters();

  @override
  Widget build(BuildContext context) {
    final finance = FinanceScope.of(context);
    final c = context.colors;
    final cash = finance.view == 'caixa';
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (finance.hasSeveralOwners)
            Wrap(
              spacing: 8,
              children: [
                for (final option in const [
                  ('todas', 'Tudo'),
                  ('pessoal', 'Pessoal'),
                  ('empresa', 'Empresas'),
                ])
                  ChoiceChip(
                    label: Text(option.$2),
                    selected: finance.ownerFilter == option.$1,
                    onSelected: (_) => finance.setOwnerFilter(option.$1),
                  ),
              ],
            ),
          const SizedBox(height: 8),
          SegmentedButton<String>(
            segments: const [
              ButtonSegment(value: 'competencia', label: Text('Gastos')),
              ButtonSegment(value: 'caixa', label: Text('Caixa')),
            ],
            selected: {finance.view},
            showSelectedIcon: false,
            onSelectionChanged: (value) => finance.setView(value.first),
          ),
          const SizedBox(height: 6),
          Text(
            cash
                ? 'Caixa: só o que entrou e saiu das contas. As compras do '
                      'cartão aparecem quando você paga a fatura.'
                : 'Gastos: o que você gastou, quando gastou (compras do cartão '
                      'contam na data da compra; pagar a fatura não conta de novo).',
            style: TextStyle(color: c.muted, fontSize: 12, height: 1.35),
          ),
        ],
      ),
    );
  }
}

class _SummaryContent extends StatelessWidget {
  const _SummaryContent({required this.summary});
  final FinancialSummary summary;

  @override
  Widget build(BuildContext context) {
    final categories = [
      for (final entry in summary.expensesByCategory.entries)
        _categoryFor(entry.key, entry.value),
    ]..sort((a, b) => b.amount.compareTo(a.amount));
    final maxAmount = categories.isEmpty ? 1.0 : categories.first.amount;

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
          child: Reveal(
            index: 1,
            child: _BalanceCard(
              balance: summary.netBalance,
              income: summary.totalIncome,
              expenses: summary.totalExpenses,
              savingsRate: summary.savingsFraction,
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 28, 20, 12),
          child: Reveal(
            index: 2,
            child: Align(
              alignment: Alignment.centerLeft,
              child: Semantics(
                header: true,
                child: Text(
                  'Para onde foi o dinheiro',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
            ),
          ),
        ),
        if (categories.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Text(
              'Nenhuma despesa nos extratos importados.',
              style: TextStyle(color: context.colors.muted),
            ),
          ),
        for (var i = 0; i < categories.length; i++)
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 10),
            child: Reveal(
              index: 3 + i,
              child: _CategoryTile(
                category: categories[i],
                share: maxAmount <= 0 ? 0 : categories[i].amount / maxAmount,
              ),
            ),
          ),
        if (summary.topMerchants.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 24, 20, 12),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Semantics(
                header: true,
                child: Text(
                  'Onde você mais gastou',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
            ),
          ),
          for (final item in summary.topMerchants)
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
              child: _MerchantRow(
                merchant: item,
                share: summary.topMerchants.first.total <= 0
                    ? 0
                    : item.total / summary.topMerchants.first.total,
              ),
            ),
        ],
        if (summary.byAccount.length > 1) ...[
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 24, 20, 12),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Semantics(
                header: true,
                child: Text(
                  'Por conta',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
            ),
          ),
          for (final account in summary.byAccount)
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
              child: _AccountRow(account: account),
            ),
        ],
        const _InstallmentsCard(),
        if (summary.excludedCount > 0)
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  Icons.info_outline_rounded,
                  size: 18,
                  color: context.colors.muted,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    '${summary.excludedCount} '
                    '${summary.excludedCount == 1 ? 'movimentação ficou' : 'movimentações ficaram'}'
                    ' fora dos totais (pagamento de fatura, resgates e '
                    'transferências entre suas contas), para não contar o mesmo '
                    'dinheiro duas vezes.',
                    style: TextStyle(
                      color: context.colors.muted,
                      fontSize: 13,
                      height: 1.4,
                    ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

class _AccountRow extends StatelessWidget {
  const _AccountRow({required this.account});
  final AccountTotals account;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Semantics(
      label:
          '${account.label}: receitas ${_brl.format(account.income)}, '
          'despesas ${_brl.format(account.expenses)}',
      child: ExcludeSemantics(
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: c.surface,
            borderRadius: BorderRadius.circular(AppTheme.radius),
            border: Border.all(color: c.line),
          ),
          child: Row(
            children: [
              Icon(
                account.isCard
                    ? Icons.credit_card_rounded
                    : Icons.account_balance_rounded,
                color: c.accent,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  account.label,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    '+ ${_brl.format(account.income)}',
                    style: TextStyle(color: c.muted, fontSize: 13),
                  ),
                  Text(
                    '− ${_brl.format(account.expenses)}',
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Resumo dos parcelamentos dos cartões, com atalho para a tela de controle.
class _InstallmentsCard extends StatelessWidget {
  const _InstallmentsCard();

  @override
  Widget build(BuildContext context) {
    final data = FinanceScope.of(context).installments;
    if (data.isEmpty || data.activeCount == 0) return const SizedBox.shrink();
    final c = context.colors;
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 0),
      child: Semantics(
        button: true,
        label:
            'Parcelamentos: ${_brl.format(data.totalRemaining)} ainda a pagar '
            'em ${data.activeCount} compras',
        child: ExcludeSemantics(
          child: Material(
            color: c.tint,
            borderRadius: BorderRadius.circular(AppTheme.radius),
            child: InkWell(
              borderRadius: BorderRadius.circular(AppTheme.radius),
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => const InstallmentsScreen(),
                ),
              ),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    Icon(Icons.credit_score_rounded, color: c.accent, size: 28),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Parcelamentos',
                            style: TextStyle(fontWeight: FontWeight.w800),
                          ),
                          Text(
                            '${_brl.format(data.totalRemaining)} ainda a pagar · '
                            '${data.activeCount} '
                            '${data.activeCount == 1 ? 'compra' : 'compras'}',
                            style: TextStyle(color: c.muted),
                          ),
                        ],
                      ),
                    ),
                    Icon(Icons.chevron_right_rounded, color: c.muted),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _MerchantRow extends StatelessWidget {
  const _MerchantRow({required this.merchant, required this.share});
  final MerchantTotal merchant;
  final double share;

  @override
  Widget build(BuildContext context) => Semantics(
    label: '${merchant.merchant}, ${_brl.format(merchant.total)}',
    child: ExcludeSemantics(
      child: Row(
        children: [
          Expanded(
            flex: 7,
            child: Text(
              merchant.merchant,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            flex: 3,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: LinearProgressIndicator(
                value: share.clamp(0.0, 1.0),
                minHeight: 8,
                backgroundColor: context.colors.line,
                valueColor: AlwaysStoppedAnimation(context.colors.accent),
              ),
            ),
          ),
          const SizedBox(width: 12),
          SizedBox(
            width: 92,
            child: Text(
              _brl.format(merchant.total),
              textAlign: TextAlign.end,
              style: const TextStyle(
                fontWeight: FontWeight.w800,
                fontFeatures: [FontFeature.tabularFigures()],
              ),
            ),
          ),
        ],
      ),
    ),
  );
}

class _MessageCard extends StatelessWidget {
  const _MessageCard({
    required this.icon,
    required this.title,
    required this.text,
    this.action,
    this.onAction,
  });

  final IconData icon;
  final String title;
  final String text;
  final String? action;
  final Future<void> Function()? onAction;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 0),
      child: Container(
        padding: const EdgeInsets.all(22),
        decoration: BoxDecoration(
          color: c.tint,
          borderRadius: BorderRadius.circular(24),
        ),
        child: Column(
          children: [
            Icon(icon, size: 36, color: c.accent),
            const SizedBox(height: 12),
            Text(
              title,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontWeight: FontWeight.w800,
                fontSize: 16,
                color: c.ink,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              text,
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 13.5, height: 1.4, color: c.ink),
            ),
            if (action != null) ...[
              const SizedBox(height: 16),
              FilledButton(
                onPressed: onAction,
                style: FilledButton.styleFrom(
                  backgroundColor: AppTheme.gold,
                  foregroundColor: AppTheme.forest,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                ),
                child: Text(
                  action!,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _BalanceCard extends StatelessWidget {
  const _BalanceCard({
    required this.balance,
    required this.income,
    required this.expenses,
    required this.savingsRate,
  });

  final double balance;
  final double income;
  final double expenses;
  final double savingsRate;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(28),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: const [
            Color(0xFF3F6666),
            Color(0xFF2F4F4F),
            Color(0xFF1B3232),
          ],
        ),
        boxShadow: [
          BoxShadow(
            color: AppTheme.forest.withValues(alpha: 0.28),
            blurRadius: 30,
            offset: const Offset(0, 14),
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: Stack(
        children: [
          Positioned(
            right: -40,
            top: -40,
            child: _Ring(
              size: 160,
              color: Colors.white.withValues(alpha: 0.07),
            ),
          ),
          Positioned(right: 22, top: 22, child: const SpinningCoin(size: 70)),
          Padding(
            padding: const EdgeInsets.all(22),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Saldo líquido do período',
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.75),
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                CountUp(
                  value: balance,
                  format: _brl.format,
                  style: const TextStyle(
                    fontFamily: AppTheme.fontFamily,
                    fontSize: 38,
                    fontWeight: FontWeight.w800,
                    letterSpacing: -1,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 18),
                _SavingsBar(rate: savingsRate),
                const SizedBox(height: 18),
                Row(
                  children: [
                    Expanded(
                      child: _Metric(
                        icon: Icons.south_west_rounded,
                        label: 'Receitas',
                        value: _brl.format(income),
                      ),
                    ),
                    Expanded(
                      child: _Metric(
                        icon: Icons.north_east_rounded,
                        label: 'Despesas',
                        value: _brl.format(expenses),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Ring extends StatelessWidget {
  const _Ring({required this.size, required this.color});
  final double size;
  final Color color;

  @override
  Widget build(BuildContext context) => ExcludeSemantics(
    child: Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        border: Border.all(color: color, width: 18),
      ),
    ),
  );
}

class _SavingsBar extends StatelessWidget {
  const _SavingsBar({required this.rate});
  final double rate;

  @override
  Widget build(BuildContext context) {
    final pct = NumberFormat.percentPattern('pt_BR');
    pct.maximumFractionDigits = 1;
    return Semantics(
      label: 'Taxa de poupança ${pct.format(rate)}',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                'Poupança',
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.75),
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const Spacer(),
              CountUp(
                value: rate,
                format: pct.format,
                style: const TextStyle(
                  fontFamily: AppTheme.fontFamily,
                  color: Colors.white,
                  fontWeight: FontWeight.w800,
                  fontSize: 13,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: rate),
              duration: Motion.slow * 1.6,
              curve: Motion.emphasized,
              builder: (_, v, __) => LinearProgressIndicator(
                value: v,
                minHeight: 8,
                backgroundColor: Colors.white.withValues(alpha: 0.18),
                valueColor: const AlwaysStoppedAnimation(AppTheme.gold),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({required this.icon, required this.label, required this.value});
  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      Container(
        width: 34,
        height: 34,
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.14),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Icon(icon, size: 18, color: Colors.white),
      ),
      const SizedBox(width: 10),
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              label,
              style: TextStyle(
                color: Colors.white.withValues(alpha: 0.7),
                fontSize: 11,
              ),
            ),
            FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerLeft,
              child: Text(
                value,
                maxLines: 1,
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w700,
                  fontSize: 14,
                ),
              ),
            ),
          ],
        ),
      ),
    ],
  );
}

class _CategoryTile extends StatelessWidget {
  const _CategoryTile({required this.category, required this.share});
  final _Category category;
  final double share;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.colors.surface,
        borderRadius: BorderRadius.circular(AppTheme.radius),
        border: Border.all(color: context.colors.line),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: category.color.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(category.icon, color: category.color, size: 22),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  category.name,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 15,
                  ),
                ),
              ),
              Text(
                _brl.format(category.amount),
                style: const TextStyle(
                  fontWeight: FontWeight.w800,
                  fontSize: 15,
                  fontFeatures: [FontFeature.tabularFigures()],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: share),
              duration: Motion.slow * 1.4,
              curve: Motion.emphasized,
              builder: (_, v, __) => LinearProgressIndicator(
                value: v,
                minHeight: 6,
                backgroundColor: category.color.withValues(alpha: 0.10),
                valueColor: AlwaysStoppedAnimation(category.color),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
