import 'package:flutter/material.dart';

import '../../../core/format.dart';
import '../../../core/theme/app_theme.dart';
import '../../finance/domain/library_models.dart';
import '../../finance/presentation/finance_controller.dart';
import '../../import_guide/presentation/import_flow_screen.dart';
import '../../installments/presentation/installments_screen.dart';
import '../../transfers/presentation/transfers_screen.dart';

String statementLine(StatementInfo statement) {
  final start = statement.periodStart;
  final end = statement.periodEnd;
  final period = start == null || end == null
      ? ''
      : '${shortDate(start)} a ${shortDate(end)}';
  final status = switch (statement.status) {
    StatementStatus.closed => statement.isCard ? 'fechada' : 'completo',
    StatementStatus.open =>
      'aberta${statement.coveredUntil == null ? '' : ' · até ${shortDate(statement.coveredUntil!)}'}',
    StatementStatus.partial =>
      'parcial${statement.coveredUntil == null ? '' : ' · até ${shortDate(statement.coveredUntil!)}'}',
    StatementStatus.unknown => 'situação desconhecida',
  };
  return [period, status].where((p) => p.isNotEmpty).join(' · ');
}

/// Pílula com a situação do arquivo (fechada, aberta, parcial).
class StatusPill extends StatelessWidget {
  const StatusPill({super.key, required this.statement});

  final StatementInfo statement;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final incomplete = statement.status.isIncomplete;
    final text = switch (statement.status) {
      StatementStatus.closed => statement.isCard ? 'Fechada' : 'Completo',
      StatementStatus.open => 'Aberta',
      StatementStatus.partial => 'Parcial',
      StatementStatus.unknown => 'Sem situação',
    };
    return Semantics(
      label: 'Situação: $text',
      child: ExcludeSemantics(
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: incomplete ? AppTheme.gold.withValues(alpha: 0.25) : c.bg,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: incomplete ? AppTheme.gold : c.line),
          ),
          child: Text(
            text,
            style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 11),
          ),
        ),
      ),
    );
  }
}

/// Folha para confirmar ou ajustar a situação de um arquivo já importado.
Future<void> showStatementSheet(
  BuildContext context,
  StatementInfo statement,
) async {
  final finance = FinanceScope.of(context);
  await showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    builder: (sheetContext) => SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              statement.isCard ? 'Situação da fatura' : 'Situação do extrato',
              style: Theme.of(sheetContext).textTheme.titleLarge,
            ),
            const SizedBox(height: 6),
            Text(statementLine(statement)),
            const SizedBox(height: 14),
            Text(
              'Para atualizar os lançamentos, importe o arquivo de novo: o app '
              'substitui o deste período.',
              style: TextStyle(color: sheetContext.colors.muted, height: 1.4),
            ),
            const SizedBox(height: 14),
            if (statement.status != StatementStatus.closed)
              FilledButton(
                onPressed: () async {
                  Navigator.pop(sheetContext);
                  await finance.confirmStatementClosed(statement, closed: true);
                },
                child: Text(
                  statement.isCard
                      ? 'Marcar como fechada'
                      : 'Marcar como completo',
                ),
              )
            else
              OutlinedButton(
                onPressed: () async {
                  Navigator.pop(sheetContext);
                  await finance.confirmStatementClosed(
                    statement,
                    closed: false,
                  );
                },
                child: Text(
                  statement.isCard
                      ? 'Na verdade ainda está aberta'
                      : 'Na verdade está incompleto',
                ),
              ),
            const SizedBox(height: 8),
            OutlinedButton(
              onPressed: () async {
                Navigator.pop(sheetContext);
                final range = await showDateRangePicker(
                  context: context,
                  firstDate: DateTime(2000),
                  lastDate: DateTime(DateTime.now().year + 2, 12, 31),
                  helpText: 'Período do arquivo',
                  saveText: 'Salvar',
                  initialDateRange:
                      statement.periodStart != null &&
                          statement.periodEnd != null
                      ? DateTimeRange(
                          start: statement.periodStart!,
                          end: statement.periodEnd!,
                        )
                      : null,
                );
                if (range != null) {
                  await finance.setStatementPeriod(
                    statement,
                    range.start,
                    range.end,
                  );
                }
              },
              child: const Text('Configurar período'),
            ),
          ],
        ),
      ),
    ),
  );
}

/// Atalhos para transferências entre contas e parcelamentos.
class ShortcutsSection extends StatelessWidget {
  const ShortcutsSection({super.key});

  @override
  Widget build(BuildContext context) {
    final finance = FinanceScope.of(context);
    final pending = finance.suggestions.length;
    final handled = finance.transfers.length;
    final installments = finance.installments;
    final hasTransfers = pending > 0 || handled > 0;
    if (!hasTransfers && installments.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
      child: Column(
        children: [
          if (hasTransfers)
            _ShortcutTile(
              icon: Icons.swap_horiz_rounded,
              title: 'Transferências entre suas contas',
              subtitle: pending > 0
                  ? '$pending ${pending == 1 ? 'para confirmar' : 'para confirmar'}'
                        '${handled > 0 ? ' · $handled já tratadas' : ''}'
                  : '$handled ${handled == 1 ? 'já tratada' : 'já tratadas'}',
              highlight: pending > 0,
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => const TransfersScreen(),
                ),
              ),
            ),
          if (!installments.isEmpty)
            _ShortcutTile(
              icon: Icons.credit_score_rounded,
              title: 'Parcelamentos',
              subtitle:
                  '${brl.format(installments.totalRemaining)} a pagar · '
                  '${installments.activeCount} ${installments.activeCount == 1 ? 'compra' : 'compras'}',
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => const InstallmentsScreen(),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _ShortcutTile extends StatelessWidget {
  const _ShortcutTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.highlight = false,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  final bool highlight;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Semantics(
        button: true,
        label: '$title. $subtitle',
        child: ExcludeSemantics(
          child: Material(
            color: highlight ? AppTheme.gold.withValues(alpha: 0.2) : c.surface,
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
                    Icon(icon, color: c.accent),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            title,
                            style: const TextStyle(fontWeight: FontWeight.w800),
                          ),
                          Text(
                            subtitle,
                            style: TextStyle(color: c.muted, fontSize: 13),
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

/// Avisos de cobertura: arquivos ainda abertos e períodos sem arquivo.
class CoverageNotice extends StatelessWidget {
  const CoverageNotice({super.key});

  @override
  Widget build(BuildContext context) {
    final finance = FinanceScope.of(context);
    final open = finance.incompleteStatements;
    final gaps = <String>[
      for (final entry in finance.statements.coverage.values)
        for (final gap in entry.gaps)
          '${entry.label}: faltam arquivos de ${shortDate(gap.from)} a ${shortDate(gap.to)}',
    ];
    if (open.isEmpty && gaps.isEmpty) return const SizedBox.shrink();
    final c = context.colors;
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppTheme.gold.withValues(alpha: 0.2),
          borderRadius: BorderRadius.circular(AppTheme.radius),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.info_outline_rounded, color: c.ink),
                const SizedBox(width: 8),
                const Expanded(
                  child: Text(
                    'Valores parciais',
                    style: TextStyle(fontWeight: FontWeight.w800),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            for (final s in open)
              Text(
                '${s.isCard ? 'Fatura aberta' : 'Extrato parcial'}'
                '${s.coveredUntil == null ? '' : ': lançamentos até ${shortDate(s.coveredUntil!)}'}. '
                'Reimporte quando fechar.',
              ),
            for (final g in gaps) Text(g),
          ],
        ),
      ),
    );
  }
}

/// Contas e cartões cadastrados, com o dono (pessoal ou empresa) editável.
class AccountsSection extends StatelessWidget {
  const AccountsSection({super.key});

  @override
  Widget build(BuildContext context) {
    final finance = FinanceScope.of(context);
    final accounts = finance.accounts;
    if (accounts.isEmpty) return const SizedBox.shrink();
    final c = context.colors;
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Semantics(
            header: true,
            child: const Text(
              'Contas',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
            ),
          ),
          const SizedBox(height: 10),
          for (final account in accounts)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Container(
                padding: const EdgeInsets.fromLTRB(14, 6, 6, 6),
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
                        account.displayLabel,
                        style: const TextStyle(fontWeight: FontWeight.w700),
                      ),
                    ),
                    PopupMenuButton<AccountOwner>(
                      tooltip: 'Dono da conta',
                      onSelected: (owner) =>
                          finance.setAccountOwner(account.id, owner),
                      itemBuilder: (_) => [
                        for (final owner in AccountOwner.values)
                          CheckedPopupMenuItem(
                            value: owner,
                            checked: account.owner == owner,
                            child: Text(owner.label),
                          ),
                      ],
                      child: Padding(
                        padding: const EdgeInsets.all(8),
                        child: Chip(
                          avatar: Icon(
                            account.owner == AccountOwner.business
                                ? Icons.business_center_rounded
                                : Icons.person_rounded,
                            size: 16,
                          ),
                          label: Text(
                            account.owner == null
                                ? 'Definir dono'
                                : account.owner == AccountOwner.business
                                ? 'Empresa'
                                : 'Pessoal',
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// Texto curto com o banco e o rótulo da conta, para os cartões de arquivo.
String accountLine(
  StatementsData data,
  StatementInfo statement,
  List<AccountInfo> accounts,
) {
  for (final a in accounts) {
    if (a.id == statement.accountId) return a.displayLabel;
  }
  return data.coverage[statement.accountId]?.label ?? '';
}

// Usado por testes para abrir o fluxo com o tipo certo de dono.
String ownerText(AccountOwner owner, String? institution) =>
    ownerLabel(owner, institution);
