import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/app_motion.dart';
import '../../../core/widgets/screen_header.dart';
import '../../../core/widgets/coin.dart';

final _brl = NumberFormat.currency(locale: 'pt_BR', symbol: 'R\$');

class _Category {
  const _Category(this.name, this.amount, this.icon, this.color);
  final String name;
  final double amount;
  final IconData icon;
  final Color color;
}

const _categories = [
  _Category('Moradia', 1500, Icons.home_rounded, Color(0xFF2F6FB0)),
  _Category('Alimentação', 650.5, Icons.restaurant_rounded, Color(0xFFE9892F)),
  _Category('Transporte', 280, Icons.directions_car_rounded, AppTheme.positive),
  _Category('Lazer e Bem-Estar', 210, Icons.spa_rounded, Color(0xFF8B5CF6)),
];

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  // Dados de exemplo: o cálculo real é feito pelo backend
  // (`calculation_service.py`), nunca pelo app. Valores fixos até a tela
  // consumir `/transactions/summary`.
  static const double _income = 5000;
  static const double _expenses = 2150.5;
  static const double _balance = 2849.5;
  static const double _savingsRate = 0.5699;

  @override
  Widget build(BuildContext context) {
    const balance = _income - _expenses;
    const savingsRate = balance / _income;
    final maxAmount =
        _categories.map((c) => c.amount).reduce((a, b) => a > b ? a : b);

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: ListView(
          padding: const EdgeInsets.only(bottom: 24),
          children: [
            const Reveal(
              child: ScreenHeader(
                title: 'Seu mês em foco',
                subtitle: 'Resumo determinístico das suas contas, no aparelho.',
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
              child: const Reveal(
                index: 1,
                child: _BalanceCard(
                  balance: _balance,
                  income: _income,
                  expenses: _expenses,
                  savingsRate: _savingsRate,
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 28, 20, 12),
              child: Reveal(
                index: 2,
                child: Row(children: [
                  Expanded(
                    child: Semantics(
                      header: true,
                      child: Text('Para onde foi o dinheiro',
                          style: Theme.of(context).textTheme.titleLarge),
                    ),
                  ),
                  const _SampleTag(),
                ]),
              ),
            ),
            for (var i = 0; i < _categories.length; i++)
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 10),
                child: Reveal(
                  index: 3 + i,
                  child: _CategoryTile(
                    category: _categories[i],
                    share: _categories[i].amount / maxAmount,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _SampleTag extends StatelessWidget {
  const _SampleTag();

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: context.colors.tint,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text('dados de exemplo',
            style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                color: context.colors.accent)),
      );
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
            Color(0xFF1B3232)
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
      child: Stack(children: [
        Positioned(
          right: -40,
          top: -40,
          child: _Ring(size: 160, color: Colors.white.withValues(alpha: 0.07)),
        ),
        Positioned(
          right: 22,
          top: 22,
          child: const SpinningCoin(size: 70),
        ),
        Padding(
          padding: const EdgeInsets.all(22),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Saldo líquido do período',
                  style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.75),
                      fontSize: 13,
                      fontWeight: FontWeight.w600)),
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
              Row(children: [
                Expanded(
                    child: _Metric(
                        icon: Icons.south_west_rounded,
                        label: 'Receitas',
                        value: _brl.format(income))),
                Expanded(
                    child: _Metric(
                        icon: Icons.north_east_rounded,
                        label: 'Despesas',
                        value: _brl.format(expenses))),
              ]),
            ],
          ),
        ),
      ]),
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
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Text('Poupança',
              style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.75),
                  fontSize: 12,
                  fontWeight: FontWeight.w600)),
          const Spacer(),
          CountUp(
            value: rate,
            format: pct.format,
            style: const TextStyle(
                fontFamily: AppTheme.fontFamily,
                color: Colors.white,
                fontWeight: FontWeight.w800,
                fontSize: 13),
          ),
        ]),
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
      ]),
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({required this.icon, required this.label, required this.value});
  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Row(children: [
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
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(label,
                style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.7), fontSize: 11)),
            FittedBox(
                fit: BoxFit.scaleDown,
                alignment: Alignment.centerLeft,
                child: Text(value,
                    maxLines: 1,
                    style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w700,
                        fontSize: 14))),
          ]),
        ),
      ]);
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
      child: Column(children: [
        Row(children: [
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
            child: Text(category.name,
                style:
                    const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
          ),
          Text(_brl.format(category.amount),
              style: const TextStyle(
                  fontWeight: FontWeight.w800,
                  fontSize: 15,
                  fontFeatures: [FontFeature.tabularFigures()])),
        ]),
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
      ]),
    );
  }
}
