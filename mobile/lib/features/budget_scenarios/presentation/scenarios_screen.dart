import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/app_motion.dart';
import '../../../core/widgets/screen_header.dart';

final _brl = NumberFormat.currency(locale: 'pt_BR', symbol: 'R\$');

class _Scenario {
  const _Scenario({
    required this.title,
    required this.income,
    required this.fixed,
    required this.variable,
    required this.savings,
    required this.margin,
    this.suggested = false,
  });
  final String title;
  final double income;
  final double fixed;
  final double variable;
  final double savings;
  final double margin;
  final bool suggested;
}

const _a = _Scenario(
  title: 'Cenário A',
  income: 6000,
  fixed: 3000,
  variable: 1800,
  savings: 800,
  margin: 400,
);
const _b = _Scenario(
  title: 'Cenário B',
  income: 6000,
  fixed: 3000,
  variable: 1400,
  savings: 1200,
  margin: 400,
  suggested: true,
);

class ScenariosScreen extends StatelessWidget {
  const ScenariosScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: ListView(
          padding: const EdgeInsets.only(bottom: 24),
          children: [
            const Reveal(
              child: ScreenHeader(
                title: 'E se eu mudasse?',
                subtitle:
                    'Compare estratégias sem abrir mão do bem-estar nem das despesas essenciais.',
              ),
            ),
            const Padding(
              padding: EdgeInsets.fromLTRB(20, 12, 20, 12),
              child: Reveal(
                index: 1,
                child: _ScenarioCard(
                  scenario: _a,
                  subtitle: 'Padrão atual',
                ),
              ),
            ),
            const Padding(
              padding: EdgeInsets.fromLTRB(20, 0, 20, 12),
              child: Reveal(
                index: 2,
                child: _ScenarioCard(
                  scenario: _b,
                  subtitle: 'Otimizado para a reserva',
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 0),
              child: Reveal(
                index: 3,
                child: _DeltaCard(
                  extraSavings: _b.savings - _a.savings,
                  lessVariable: _a.variable - _b.variable,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ScenarioCard extends StatelessWidget {
  const _ScenarioCard({required this.scenario, required this.subtitle});
  final _Scenario scenario;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    final s = scenario;
    final hi = s.suggested;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: hi ? AppTheme.emerald : context.colors.surface,
        borderRadius: BorderRadius.circular(26),
        border: Border.all(color: hi ? AppTheme.emerald : context.colors.line),
        boxShadow: hi ? AppTheme.softShadow(context) : null,
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(s.title,
                  style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                      color: hi ? Colors.white : context.colors.ink)),
              const SizedBox(height: 2),
              Text(subtitle,
                  style: TextStyle(
                      fontSize: 13,
                      color: hi
                          ? Colors.white.withValues(alpha: 0.7)
                          : context.colors.muted)),
            ]),
          ),
          if (hi)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: AppTheme.gold,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text('Sugerido',
                  style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
                      color: context.colors.ink)),
            ),
        ]),
        const SizedBox(height: 18),
        _AllocationBar(scenario: s, dark: hi),
        const SizedBox(height: 18),
        _Row('Renda mensal', s.income, null, hi),
        _Row('Despesas fixas', s.fixed, AppTheme.info, hi),
        _Row('Despesas variáveis', s.variable, const Color(0xFFE9892F), hi),
        _Row('Aporte na reserva', s.savings, AppTheme.gold, hi, strong: true),
        _Row('Margem operacional', s.margin, const Color(0xFF9AA8A2), hi),
      ]),
    );
  }
}

class _AllocationBar extends StatelessWidget {
  const _AllocationBar({required this.scenario, required this.dark});
  final _Scenario scenario;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    final s = scenario;
    final parts = [
      (s.fixed, AppTheme.info),
      (s.variable, const Color(0xFFE9892F)),
      (s.savings, AppTheme.gold),
      (s.margin, const Color(0xFF9AA8A2)),
    ];
    return Semantics(
      label: 'Distribuição da renda do ${s.title}',
      child: ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: 1),
          duration: Motion.slow * 1.6,
          curve: Motion.emphasized,
          builder: (_, t, __) => SizedBox(
            height: 12,
            child: Row(children: [
              for (final p in parts)
                Expanded(
                  flex: (p.$1 * t * 10).round().clamp(1, 100000),
                  child: Container(
                    margin: const EdgeInsets.only(right: 2),
                    color: p.$2,
                  ),
                ),
            ]),
          ),
        ),
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row(this.label, this.value, this.dot, this.dark,
      {this.strong = false});
  final String label;
  final double value;
  final Color? dot;
  final bool dark;
  final bool strong;

  @override
  Widget build(BuildContext context) {
    final fg = dark ? Colors.white : context.colors.ink;
    final sub =
        dark ? Colors.white.withValues(alpha: 0.7) : context.colors.muted;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(children: [
        SizedBox(
          width: 14,
          child: dot == null
              ? null
              : Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(color: dot, shape: BoxShape.circle),
                ),
        ),
        Expanded(
          child: Text(label,
              style: TextStyle(
                  color: strong ? fg : sub,
                  fontWeight: strong ? FontWeight.w700 : FontWeight.w500)),
        ),
        Text(_brl.format(value),
            style: TextStyle(
                color: fg,
                fontWeight: strong ? FontWeight.w800 : FontWeight.w600,
                fontFeatures: const [FontFeature.tabularFigures()])),
      ]),
    );
  }
}

class _DeltaCard extends StatelessWidget {
  const _DeltaCard({required this.extraSavings, required this.lessVariable});
  final double extraSavings;
  final double lessVariable;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: context.colors.tint,
        borderRadius: BorderRadius.circular(22),
      ),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(Icons.trending_up_rounded, color: context.colors.accent),
        const SizedBox(width: 12),
        Expanded(
          child: Text.rich(
            TextSpan(
              style: TextStyle(
                  color: context.colors.ink, height: 1.45, fontSize: 14),
              children: [
                const TextSpan(text: 'Reduzindo '),
                TextSpan(
                    text: '${_brl.format(lessVariable)} em gastos variáveis',
                    style: const TextStyle(fontWeight: FontWeight.w800)),
                const TextSpan(text: ', a reserva cresce '),
                TextSpan(
                    text: '${_brl.format(extraSavings)} por mês',
                    style: const TextStyle(fontWeight: FontWeight.w800)),
                const TextSpan(text: ', sem tocar nas despesas essenciais.'),
              ],
            ),
          ),
        ),
      ]),
    );
  }
}
