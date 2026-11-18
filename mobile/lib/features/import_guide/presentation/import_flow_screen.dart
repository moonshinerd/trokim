import 'package:flutter/material.dart';

import '../../../core/settings/settings_controller.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/app_motion.dart';
import '../../finance/domain/finance_models.dart';
import '../../finance/presentation/finance_controller.dart';
import '../../transactions/presentation/transactions_screen.dart';
import '../domain/import_guides.dart';

enum _Phase { bank, kind, tutorial, importing, done, failed }

/// Fluxo guiado de importação: banco, tipo de arquivo, tutorial e resumo.
///
/// Em qualquer tela o usuário pode pular o tutorial e ir direto ao arquivo
/// ("Já tenho o arquivo"). Com o tutorial desligado em Ajustes, o app abre o
/// seletor de arquivos assim que a tela aparece.
class ImportFlowScreen extends StatefulWidget {
  const ImportFlowScreen({
    super.key,
    this.pickFile,
    this.startAtPicker = false,
  });

  /// Troca o seletor de arquivos (testes).
  final StatementPicker? pickFile;

  /// Abre o seletor logo de início (tutorial desligado em Ajustes).
  final bool startAtPicker;

  @override
  State<ImportFlowScreen> createState() => _ImportFlowScreenState();
}

class _ImportFlowScreenState extends State<ImportFlowScreen> {
  _Phase _phase = _Phase.bank;
  NubankStatementKind? _kind;
  int _step = 0;
  bool _dontShowAgain = false;
  ImportResult? _result;
  String? _error;

  @override
  void initState() {
    super.initState();
    if (widget.startAtPicker) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _pickAndImport());
    }
  }

  void _go(_Phase phase) => setState(() => _phase = phase);

  Future<void> _pickAndImport() async {
    final finance = FinanceScope.of(context);
    if (finance.importing) return;
    final PickedStatement? picked;
    try {
      picked = await (widget.pickFile ?? pickStatementFile)();
    } on Object {
      if (!mounted) return;
      setState(() {
        _error = 'Não foi possível abrir o seletor de arquivos.';
        _phase = _Phase.failed;
      });
      return;
    }
    if (!mounted) return;
    if (picked == null) {
      // Cancelou o seletor: volta para onde estava, sem erro.
      if (widget.startAtPicker && _phase == _Phase.bank) {
        Navigator.of(context).maybePop();
      }
      return;
    }
    _go(_Phase.importing);
    try {
      final result = await finance.importStatement(
        picked.name,
        picked.readBytes,
      );
      if (!mounted) return;
      setState(() {
        _result = result;
        _phase = _Phase.done;
      });
    } on ImportFailure catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _phase = _Phase.failed;
      });
    }
  }

  void _skipTutorial() {
    _saveDontShowAgain();
    _pickAndImport();
  }

  void _saveDontShowAgain() {
    if (_dontShowAgain) {
      SettingsScope.maybeOf(context)?.setShowImportTutorial(false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final reduced = Motion.reduced(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Importar extrato'),
        leading: _phase == _Phase.importing
            ? const SizedBox.shrink()
            : const CloseButton(),
      ),
      body: SafeArea(
        child: AnimatedSwitcher(
          duration: reduced ? Duration.zero : Motion.base,
          switchInCurve: Motion.enter,
          child: KeyedSubtree(
            key: ValueKey('$_phase-$_step'),
            child: switch (_phase) {
              _Phase.bank => _BankStep(
                onNubank: () => _go(_Phase.kind),
                onOther: _pickAndImport,
                onHaveFile: _pickAndImport,
              ),
              _Phase.kind => _KindStep(
                onSelected: (kind) => setState(() {
                  _kind = kind;
                  _step = 0;
                  _phase = _Phase.tutorial;
                }),
                onSkip: _skipTutorial,
                onBack: () => _go(_Phase.bank),
              ),
              _Phase.tutorial => _TutorialStep(
                steps: nubankGuide(_kind!),
                index: _step,
                dontShowAgain: _dontShowAgain,
                onDontShowAgain: (v) => setState(() => _dontShowAgain = v),
                onBack: () =>
                    _step == 0 ? _go(_Phase.kind) : setState(() => _step--),
                onNext: () => setState(() => _step++),
                onSkip: _skipTutorial,
                onPick: () {
                  _saveDontShowAgain();
                  _pickAndImport();
                },
              ),
              _Phase.importing => const _ImportingStep(),
              _Phase.done => _SummaryStep(
                result: _result!,
                onDone: () => Navigator.of(context).pop(_result),
              ),
              _Phase.failed => _FailedStep(
                message: _error ?? 'Não foi possível importar o arquivo.',
                onRetry: _pickAndImport,
                onTutorial: () => _go(_Phase.bank),
              ),
            },
          ),
        ),
      ),
    );
  }
}

class _StepLayout extends StatelessWidget {
  const _StepLayout({
    required this.title,
    this.subtitle,
    required this.children,
    this.actions = const [],
  });

  final String title;
  final String? subtitle;
  final List<Widget> children;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Column(
      children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 12),
            children: [
              Semantics(
                header: true,
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.headlineSmall
                      ?.copyWith(fontWeight: FontWeight.w800),
                ),
              ),
              if (subtitle != null) ...[
                const SizedBox(height: 6),
                Text(subtitle!, style: TextStyle(color: c.muted, height: 1.4)),
              ],
              const SizedBox(height: 18),
              ...children,
            ],
          ),
        ),
        if (actions.isNotEmpty)
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: actions,
            ),
          ),
      ],
    );
  }
}

class _OptionCard extends StatelessWidget {
  const _OptionCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Semantics(
        button: true,
        label: '$title. $subtitle',
        child: ExcludeSemantics(
          child: Material(
            color: c.tint,
            borderRadius: BorderRadius.circular(20),
            child: InkWell(
              borderRadius: BorderRadius.circular(20),
              onTap: onTap,
              child: Padding(
                padding: const EdgeInsets.all(18),
                child: Row(
                  children: [
                    Icon(icon, size: 30, color: c.accent),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            title,
                            style: const TextStyle(
                              fontSize: 17,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(subtitle, style: TextStyle(color: c.muted)),
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

class _BankStep extends StatelessWidget {
  const _BankStep({
    required this.onNubank,
    required this.onOther,
    required this.onHaveFile,
  });

  final VoidCallback onNubank;
  final VoidCallback onOther;
  final VoidCallback onHaveFile;

  @override
  Widget build(BuildContext context) => _StepLayout(
    title: 'De qual banco é o arquivo?',
    subtitle: 'Mostramos como baixar o arquivo certo. Você pode pular.',
    children: [
      _OptionCard(
        icon: Icons.account_balance_rounded,
        title: 'Nubank',
        subtitle: 'Fatura do cartão e extrato da conta',
        onTap: onNubank,
      ),
      _OptionCard(
        icon: Icons.folder_open_rounded,
        title: 'Outro banco',
        subtitle: 'Arquivo OFX ou PDF que você já tem',
        onTap: onOther,
      ),
    ],
    actions: [
      OutlinedButton.icon(
        onPressed: onHaveFile,
        icon: const Icon(Icons.upload_file_rounded),
        label: const Text('Já tenho o arquivo'),
      ),
    ],
  );
}

class _KindStep extends StatelessWidget {
  const _KindStep({
    required this.onSelected,
    required this.onSkip,
    required this.onBack,
  });

  final ValueChanged<NubankStatementKind> onSelected;
  final VoidCallback onSkip;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) => _StepLayout(
    title: 'O que você quer importar?',
    subtitle: 'Cada um é baixado de um lugar diferente no app do Nubank.',
    children: [
      _OptionCard(
        icon: Icons.credit_card_rounded,
        title: 'Fatura do cartão',
        subtitle: 'Compras, parcelas e pagamentos do cartão',
        onTap: () => onSelected(NubankStatementKind.card),
      ),
      _OptionCard(
        icon: Icons.account_balance_wallet_rounded,
        title: 'Extrato da conta',
        subtitle: 'Pix, compras no débito e movimentações',
        onTap: () => onSelected(NubankStatementKind.account),
      ),
    ],
    actions: [
      FilledButton(onPressed: onSkip, child: const Text('Pular tutorial')),
      TextButton(onPressed: onBack, child: const Text('Voltar')),
    ],
  );
}

class _TutorialStep extends StatelessWidget {
  const _TutorialStep({
    required this.steps,
    required this.index,
    required this.dontShowAgain,
    required this.onDontShowAgain,
    required this.onBack,
    required this.onNext,
    required this.onSkip,
    required this.onPick,
  });

  final List<GuideStep> steps;
  final int index;
  final bool dontShowAgain;
  final ValueChanged<bool> onDontShowAgain;
  final VoidCallback onBack;
  final VoidCallback onNext;
  final VoidCallback onSkip;
  final VoidCallback onPick;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final step = steps[index];
    final last = index == steps.length - 1;
    return _StepLayout(
      title: step.title,
      children: [
        Semantics(
          label: 'Passo ${index + 1} de ${steps.length}',
          child: LinearProgressIndicator(
            value: (index + 1) / steps.length,
            minHeight: 6,
            borderRadius: BorderRadius.circular(6),
          ),
        ),
        const SizedBox(height: 6),
        Text(
          'Passo ${index + 1} de ${steps.length}',
          style: TextStyle(color: c.muted, fontSize: 12),
        ),
        const SizedBox(height: 28),
        Center(
          child: Container(
            width: 120,
            height: 120,
            decoration: BoxDecoration(color: c.tint, shape: BoxShape.circle),
            child: ExcludeSemantics(
              child: Icon(step.icon, size: 56, color: c.accent),
            ),
          ),
        ),
        const SizedBox(height: 28),
        Text(
          step.description,
          style: const TextStyle(fontSize: 17, height: 1.45),
        ),
        if (last) ...[
          const SizedBox(height: 20),
          CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            controlAffinity: ListTileControlAffinity.leading,
            value: dontShowAgain,
            onChanged: (v) => onDontShowAgain(v ?? false),
            title: const Text('Não mostrar este tutorial de novo'),
            subtitle: const Text('Você pode reativar em Ajustes.'),
          ),
        ],
      ],
      actions: [
        FilledButton(
          onPressed: last ? onPick : onNext,
          child: Text(last ? 'Escolher arquivo' : 'Próximo'),
        ),
        Row(
          children: [
            TextButton(onPressed: onBack, child: const Text('Voltar')),
            const Spacer(),
            if (!last)
              TextButton(
                onPressed: onSkip,
                child: const Text('Pular tutorial'),
              ),
          ],
        ),
      ],
    );
  }
}

class _ImportingStep extends StatelessWidget {
  const _ImportingStep();

  @override
  Widget build(BuildContext context) => Center(
    child: Semantics(
      liveRegion: true,
      label: 'Importando o arquivo',
      child: const Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          CircularProgressIndicator(),
          SizedBox(height: 16),
          Text('Lendo o arquivo…'),
        ],
      ),
    ),
  );
}

class _SummaryStep extends StatelessWidget {
  const _SummaryStep({required this.result, required this.onDone});

  final ImportResult result;
  final VoidCallback onDone;

  String _plural(int n, String one, String many) => '$n ${n == 1 ? one : many}';

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final detected = result.institutionLabel == null
        ? null
        : 'Detectei: ${result.institutionLabel}'
              '${result.kindLabel == null ? '' : ', ${result.kindLabel}'}';
    return _StepLayout(
      title: 'Pronto!',
      subtitle: result.filename,
      children: [
        if (detected != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 14),
            child: Row(
              children: [
                Icon(Icons.verified_rounded, color: c.accent),
                const SizedBox(width: 8),
                Expanded(child: Text(detected)),
              ],
            ),
          ),
        _SummaryLine(
          icon: Icons.receipt_long_rounded,
          text: _plural(
            result.importedCount,
            'lançamento lido',
            'lançamentos lidos',
          ),
        ),
        if (result.duplicateCount > 0)
          _SummaryLine(
            icon: Icons.copy_all_rounded,
            text:
                '${_plural(result.duplicateCount, 'repetido ignorado', 'repetidos ignorados')}'
                ' (já estavam importados)',
          ),
        if (result.excludedCount > 0)
          _SummaryLine(
            icon: Icons.swap_horiz_rounded,
            text:
                '${_plural(result.excludedCount, 'movimentação fora dos totais', 'movimentações fora dos totais')}'
                ' (pagamento de fatura, resgates e transferências próprias)',
          ),
        if (result.uncategorizedCount > 0)
          _SummaryLine(
            icon: Icons.category_outlined,
            text:
                '${_plural(result.uncategorizedCount, 'gasto sem categoria', 'gastos sem categoria')}'
                ' (aparecem como "Outros" no Resumo)',
          ),
      ],
      actions: [FilledButton(onPressed: onDone, child: const Text('Concluir'))],
    );
  }
}

class _SummaryLine extends StatelessWidget {
  const _SummaryLine({required this.icon, required this.text});
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 22, color: context.colors.muted),
        const SizedBox(width: 12),
        Expanded(child: Text(text, style: const TextStyle(height: 1.4))),
      ],
    ),
  );
}

class _FailedStep extends StatelessWidget {
  const _FailedStep({
    required this.message,
    required this.onRetry,
    required this.onTutorial,
  });

  final String message;
  final VoidCallback onRetry;
  final VoidCallback onTutorial;

  @override
  Widget build(BuildContext context) => _StepLayout(
    title: 'Não deu para importar',
    children: [
      Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.error_outline_rounded, color: AppTheme.negative),
          const SizedBox(width: 12),
          Expanded(child: Text(message, style: const TextStyle(height: 1.4))),
        ],
      ),
    ],
    actions: [
      FilledButton(
        onPressed: onRetry,
        child: const Text('Escolher outro arquivo'),
      ),
      TextButton(onPressed: onTutorial, child: const Text('Ver tutorial')),
    ],
  );
}
