import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/format.dart';
import '../../../core/settings/settings_controller.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/app_motion.dart';
import '../../categories/presentation/category_review_screen.dart';
import '../../finance/domain/finance_models.dart';
import '../../finance/domain/library_models.dart';
import '../../finance/presentation/finance_controller.dart';
import '../../transactions/presentation/transactions_screen.dart';
import '../../transfers/presentation/transfers_screen.dart';
import '../domain/import_guides.dart';

enum _Phase {
  bank,
  product,
  kind,
  tutorial,
  reading,
  decide,
  importing,
  done,
  failed,
}

/// Nome do dono da conta conforme o banco ("Nubank Empresas" só existe no Nubank).
String ownerLabel(AccountOwner owner, String? institution) =>
    owner == AccountOwner.business && institution != 'nubank'
    ? 'Conta de empresa'
    : owner.label;

/// Fluxo guiado de importação: banco, conta, tipo de arquivo, tutorial, leitura, decisões e
/// resumo.
///
/// Em qualquer tela o usuário pode pular o tutorial e ir direto ao arquivo ("Já tenho o
/// arquivo"). Com o tutorial desligado em Ajustes, o app abre o seletor de arquivos assim que a
/// tela aparece. Um arquivo recebido por "Compartilhar" ([initialFile]) entra direto na leitura.
class ImportFlowScreen extends StatefulWidget {
  const ImportFlowScreen({
    super.key,
    this.pickFile,
    this.startAtPicker = false,
    this.initialFile,
    this.onRequestSupport,
  });

  /// Troca o seletor de arquivos (testes).
  final StatementPicker? pickFile;

  /// Abre o seletor logo de início (tutorial desligado em Ajustes).
  final bool startAtPicker;

  /// Arquivo que já chegou (compartilhado de outro app): vai direto para a leitura.
  final PickedStatement? initialFile;

  /// Callback opcional para pedir suporte a um banco (testes e extensão).
  final VoidCallback? onRequestSupport;

  @override
  State<ImportFlowScreen> createState() => _ImportFlowScreenState();
}

class _ImportFlowScreenState extends State<ImportFlowScreen> {
  _Phase _phase = _Phase.bank;
  GuideBank? _bank;
  NubankStatementKind? _kind;
  AccountOwner? _owner;
  int _step = 0;
  bool _dontShowAgain = false;
  PickedStatement? _picked;
  Inspection? _inspection;
  ImportResult? _result;
  StatementInfo? _statement;
  String? _statementNote;
  String? _error;

  @override
  void initState() {
    super.initState();
    if (widget.initialFile != null) {
      _picked = widget.initialFile;
      WidgetsBinding.instance.addPostFrameCallback((_) => _inspect());
    } else if (widget.startAtPicker) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _pickAndInspect());
    }
  }

  void _go(_Phase phase) => setState(() => _phase = phase);

  String? get _expectKind => switch (_kind) {
    NubankStatementKind.card => 'cartao',
    NubankStatementKind.account => 'conta',
    null => null,
  };

  Future<void> _pickAndInspect() async {
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
    _picked = picked;
    await _inspect();
  }

  /// Lê o arquivo sem importar. Só pergunta ao usuário quando há algo a decidir.
  Future<void> _inspect() async {
    final picked = _picked;
    if (picked == null) return;
    final finance = FinanceScope.of(context);
    _go(_Phase.reading);
    try {
      final inspection = await finance.inspect(
        picked.name,
        picked.readBytes,
        owner: _owner,
        expectKind: _expectKind,
      );
      if (!mounted) return;
      _inspection = inspection;
      if (inspection.needsDecision) {
        _go(_Phase.decide);
        return;
      }
      await _import(
        owner: _owner ?? inspection.detectedOwner ?? inspection.knownOwner,
      );
    } on ImportFailure catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _phase = _Phase.failed;
      });
    }
  }

  Future<void> _import({AccountOwner? owner, bool confirmed = false}) async {
    final picked = _picked;
    if (picked == null) return;
    final finance = FinanceScope.of(context);
    _go(_Phase.importing);
    try {
      final result = await finance.importStatement(
        picked.name,
        picked.readBytes,
        owner: owner,
        expectKind: _expectKind,
        confirmed: confirmed,
      );
      if (!mounted) return;
      setState(() {
        _result = result;
        _statement = result.statement;
        _statementNote = null;
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
    _pickAndInspect();
  }

  void _saveDontShowAgain() {
    if (_dontShowAgain) {
      SettingsScope.maybeOf(context)?.setShowImportTutorial(false);
    }
  }

  void _resetFile() {
    _picked = null;
    _inspection = null;
    _pickAndInspect();
  }

  List<GuideStep> get _guide => getGuideForBank(
    _bank ?? GuideBank.nubank,
    _kind ?? NubankStatementKind.card,
    business: _owner == AccountOwner.business,
  );

  @override
  Widget build(BuildContext context) {
    final reduced = Motion.reduced(context);
    final busy = _phase == _Phase.importing || _phase == _Phase.reading;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Importar extrato'),
        leading: busy ? const SizedBox.shrink() : const CloseButton(),
      ),
      body: SafeArea(
        child: AnimatedSwitcher(
          duration: reduced ? Duration.zero : Motion.base,
          switchInCurve: Motion.enter,
          child: KeyedSubtree(
            key: ValueKey('$_phase-$_step'),
            child: switch (_phase) {
              _Phase.bank => _BankStep(
                onSelectBank: (bank) {
                  _bank = bank;
                  if (bank == GuideBank.nubank) {
                    _go(_Phase.product);
                  } else {
                    _owner = AccountOwner.personal;
                    _go(_Phase.kind);
                  }
                },
                onOther: () {
                  _bank = GuideBank.other;
                  _pickAndInspect();
                },
                onHaveFile: _pickAndInspect,
                onRequestSupport: widget.onRequestSupport,
              ),
              _Phase.product => _ProductStep(
                onSelected: (owner) {
                  _owner = owner;
                  _go(_Phase.kind);
                },
                onSkip: _skipTutorial,
                onBack: () => _go(_Phase.bank),
              ),
              _Phase.kind => _KindStep(
                bank: _bank ?? GuideBank.nubank,
                onSelected: (kind) => setState(() {
                  _kind = kind;
                  _step = 0;
                  _phase = _Phase.tutorial;
                }),
                onSkip: _skipTutorial,
                onBack: () => _go(
                  _bank == GuideBank.nubank ? _Phase.product : _Phase.bank,
                ),
              ),
              _Phase.tutorial => _TutorialStep(
                bank: _bank ?? GuideBank.nubank,
                steps: _guide,
                index: _step,
                dontShowAgain: _dontShowAgain,
                onDontShowAgain: (v) => setState(() => _dontShowAgain = v),
                onBack: () =>
                    _step == 0 ? _go(_Phase.kind) : setState(() => _step--),
                onNext: () => setState(() => _step++),
                onSkip: _skipTutorial,
                onPick: () {
                  _saveDontShowAgain();
                  _pickAndInspect();
                },
              ),
              _Phase.reading => const _ProgressStep(
                label: 'Lendo o arquivo…',
                semantic: 'Lendo o arquivo',
              ),
              _Phase.decide => _DecideStep(
                inspection: _inspection!,
                chosenOwner: _owner,
                onImport: (owner, {required confirmed}) =>
                    _import(owner: owner, confirmed: confirmed),
                onOtherFile: _resetFile,
              ),
              _Phase.importing => const _ProgressStep(
                label: 'Importando…',
                semantic: 'Importando o arquivo',
              ),
              _Phase.done => _SummaryStep(
                result: _result!,
                statement: _statement,
                note: _statementNote,
                onStatementChanged: (statement, note) => setState(() {
                  _statement = statement;
                  _statementNote = note;
                }),
                onDone: () => Navigator.of(context).pop(_result),
              ),
              _Phase.failed => _FailedStep(
                message: _error ?? 'Não foi possível importar o arquivo.',
                onRetry: _resetFile,
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

class _SupportedBankCard extends StatelessWidget {
  const _SupportedBankCard({required this.bank, required this.onTap});

  final SupportedBankInfo bank;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final isExperimental = bank.isExperimental;
    final badgeColor = isExperimental ? AppTheme.gold : AppTheme.positive;

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Semantics(
        button: true,
        label:
            '${bank.name}, selo ${bank.supportLevel.label}. ${bank.description}. Formato aceito: ${bank.acceptedFormats}.',
        child: Material(
          color: c.tint,
          borderRadius: BorderRadius.circular(20),
          child: InkWell(
            borderRadius: BorderRadius.circular(20),
            onTap: onTap,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: [
                      Icon(bank.icon, size: 28, color: c.accent),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          bank.name,
                          style: const TextStyle(
                            fontSize: 17,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          color: badgeColor.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(
                            color: badgeColor.withValues(alpha: 0.35),
                            width: 1,
                          ),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(
                              isExperimental
                                  ? Icons.science_outlined
                                  : Icons.verified_rounded,
                              size: 14,
                              color: badgeColor,
                            ),
                            const SizedBox(width: 4),
                            Text(
                              bank.supportLevel.label,
                              style: TextStyle(
                                color: badgeColor,
                                fontWeight: FontWeight.w800,
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    bank.description,
                    style: TextStyle(color: c.muted, fontSize: 13, height: 1.3),
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      Icon(
                        Icons.description_outlined,
                        size: 14,
                        color: c.muted,
                      ),
                      const SizedBox(width: 4),
                      Expanded(
                        child: Text(
                          'Formato aceito: ${bank.acceptedFormats}',
                          style: TextStyle(
                            color: c.muted,
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                  if (bank.experimentalNotice != null) ...[
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 10,
                        vertical: 6,
                      ),
                      decoration: BoxDecoration(
                        color: AppTheme.gold.withValues(alpha: 0.10),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Icon(
                            Icons.info_outline_rounded,
                            size: 15,
                            color: AppTheme.gold,
                          ),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              bank.experimentalNotice!,
                              style: TextStyle(
                                color: c.ink,
                                fontSize: 11,
                                height: 1.3,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                  const SizedBox(height: 10),
                  Align(
                    alignment: Alignment.centerRight,
                    child: OutlinedButton.icon(
                      onPressed: onTap,
                      icon: const Icon(Icons.arrow_forward_rounded, size: 16),
                      label: const Text('Ver como exportar'),
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 14,
                          vertical: 8,
                        ),
                        visualDensity: VisualDensity.compact,
                      ),
                    ),
                  ),
                ],
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
    required this.onSelectBank,
    required this.onOther,
    required this.onHaveFile,
    this.onRequestSupport,
  });

  final ValueChanged<GuideBank> onSelectBank;
  final VoidCallback onOther;
  final VoidCallback onHaveFile;
  final VoidCallback? onRequestSupport;

  Future<void> _defaultRequestSupport() async {
    final uri = Uri.parse('https://github.com/moonshinerd/trokim/issues/new');
    try {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return _StepLayout(
      title: 'Bancos suportados',
      subtitle: 'De qual banco é o arquivo?',
      children: [
        for (final bank in supportedBanks)
          _SupportedBankCard(bank: bank, onTap: () => onSelectBank(bank.bank)),
        _OptionCard(
          icon: Icons.folder_open_rounded,
          title: 'Outro banco',
          subtitle: 'Arquivo OFX ou PDF que você já tem',
          onTap: onOther,
        ),
        Container(
          margin: const EdgeInsets.only(top: 4, bottom: 8),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: c.surface,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: c.line),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.help_outline_rounded, size: 20, color: c.accent),
                  const SizedBox(width: 8),
                  const Expanded(
                    child: Text(
                      'Banco não reconhecido?',
                      style: TextStyle(
                        fontWeight: FontWeight.w700,
                        fontSize: 14,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              Text(
                'Envie o arquivo pelo parser genérico e confira o resumo. O Trokim tenta extrair os lançamentos mesmo de outros formatos.',
                style: TextStyle(color: c.muted, fontSize: 13, height: 1.4),
              ),
              const SizedBox(height: 8),
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  onPressed: onRequestSupport ?? _defaultRequestSupport,
                  icon: const Icon(Icons.open_in_new_rounded, size: 16),
                  label: const Text('Pedir suporte a um banco'),
                ),
              ),
            ],
          ),
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
}

class _ProductStep extends StatelessWidget {
  const _ProductStep({
    required this.onSelected,
    required this.onSkip,
    required this.onBack,
  });

  final ValueChanged<AccountOwner> onSelected;
  final VoidCallback onSkip;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) => _StepLayout(
    title: 'Qual conta do Nubank?',
    subtitle: 'O arquivo não diz se é pessoal ou Empresas, então perguntamos uma vez.',
    children: [
      _OptionCard(
        icon: Icons.person_rounded,
        title: 'Pessoa física',
        subtitle: 'Sua conta e seu cartão pessoais',
        onTap: () => onSelected(AccountOwner.personal),
      ),
      _OptionCard(
        icon: Icons.business_center_rounded,
        title: 'Nubank Empresas',
        subtitle: 'Conta e cartão da sua empresa',
        onTap: () => onSelected(AccountOwner.business),
      ),
    ],
    actions: [
      FilledButton(onPressed: onSkip, child: const Text('Pular tutorial')),
      TextButton(onPressed: onBack, child: const Text('Voltar')),
    ],
  );
}

class _KindStep extends StatelessWidget {
  const _KindStep({
    required this.bank,
    required this.onSelected,
    required this.onSkip,
    required this.onBack,
  });

  final GuideBank bank;
  final ValueChanged<NubankStatementKind> onSelected;
  final VoidCallback onSkip;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    final info = getSupportedBankInfo(bank);
    final subtitle = switch (bank) {
      GuideBank.bb =>
        'A fatura do cartão e o extrato da conta saem de apps diferentes.',
      GuideBank.nubank =>
        'Cada um é baixado de um lugar diferente no app do Nubank.',
      GuideBank.picpay => 'Extrato da conta PicPay ou fatura do PicPay Card.',
      GuideBank.mercadopago =>
        'Extrato da conta Mercado Pago ou fatura do cartão.',
      GuideBank.inter =>
        'Extrato da conta em OFX ou fatura do cartão Inter em PDF.',
      GuideBank.c6 =>
        'Extrato da conta C6 em OFX ou fatura do cartão C6 em PDF.',
      GuideBank.itau =>
        'Extrato da conta corrente em OFX ou fatura do cartão Itaú em PDF.',
      _ => 'Escolha o que você quer importar.',
    };

    final cardSub = switch (bank) {
      GuideBank.bb => 'Cartão Ourocard (arquivo PDF)',
      GuideBank.picpay => 'PicPay Card (arquivo PDF)',
      GuideBank.mercadopago => 'Cartão Mercado Pago (arquivo PDF)',
      GuideBank.inter => 'Cartão Inter (arquivo PDF)',
      GuideBank.c6 => 'Cartão C6 Bank (arquivo PDF)',
      GuideBank.itau => 'Cartão de crédito Itaú (arquivo PDF)',
      _ => 'Compras, parcelas e pagamentos do cartão',
    };

    final accSub = switch (bank) {
      GuideBank.bb => 'Conta corrente (arquivo OFX)',
      GuideBank.picpay => 'Extrato da carteira PicPay (arquivo PDF)',
      GuideBank.mercadopago => 'Extrato da conta Mercado Pago (arquivo PDF)',
      GuideBank.inter => 'Conta corrente Inter (arquivo OFX)',
      GuideBank.c6 => 'Conta corrente C6 (arquivo OFX)',
      GuideBank.itau => 'Conta corrente Itaú (arquivo OFX)',
      _ => 'Pix, compras no débito e movimentações',
    };

    return _StepLayout(
      title: 'O que você quer importar?',
      subtitle: subtitle,
      children: [
        if (info?.isExperimental == true) ...[
          Container(
            margin: const EdgeInsets.only(bottom: 14),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppTheme.gold.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppTheme.gold.withValues(alpha: 0.3)),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(
                  Icons.science_outlined,
                  color: AppTheme.gold,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    info?.experimentalNotice ?? 'Suporte experimental: tutorial baseado na ajuda oficial do banco, ainda não testado em conta real.',
                    style: const TextStyle(fontSize: 12, height: 1.35),
                  ),
                ),
              ],
            ),
          ),
        ],
        _OptionCard(
          icon: Icons.credit_card_rounded,
          title: 'Fatura do cartão',
          subtitle: cardSub,
          onTap: () => onSelected(NubankStatementKind.card),
        ),
        _OptionCard(
          icon: Icons.account_balance_wallet_rounded,
          title: 'Extrato da conta',
          subtitle: accSub,
          onTap: () => onSelected(NubankStatementKind.account),
        ),
      ],
      actions: [
        FilledButton(onPressed: onSkip, child: const Text('Pular tutorial')),
        TextButton(onPressed: onBack, child: const Text('Voltar')),
      ],
    );
  }
}

class _TutorialStep extends StatelessWidget {
  const _TutorialStep({
    required this.bank,
    required this.steps,
    required this.index,
    required this.dontShowAgain,
    required this.onDontShowAgain,
    required this.onBack,
    required this.onNext,
    required this.onSkip,
    required this.onPick,
  });

  final GuideBank bank;
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
    final info = getSupportedBankInfo(bank);
    final isExperimental = info?.isExperimental ?? false;
    final step = steps[index];
    final last = index == steps.length - 1;
    return _StepLayout(
      title: step.title,
      children: [
        if (isExperimental)
          Padding(
            padding: const EdgeInsets.only(bottom: 14),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: AppTheme.gold.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: AppTheme.gold.withValues(alpha: 0.35),
                ),
              ),
              child: const Row(
                children: [
                  Icon(Icons.science_outlined, size: 16, color: AppTheme.gold),
                  SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      'Banco experimental — ajuda oficial (não testado em conta real)',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.gold,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
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

class _ProgressStep extends StatelessWidget {
  const _ProgressStep({required this.label, required this.semantic});

  final String label;
  final String semantic;

  @override
  Widget build(BuildContext context) => Center(
    child: Semantics(
      liveRegion: true,
      label: semantic,
      child: ExcludeSemantics(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(),
            const SizedBox(height: 16),
            Text(label),
          ],
        ),
      ),
    ),
  );
}

/// O detector achou algo para o usuário decidir antes de importar: dono da conta
/// (pessoal × Empresas), tipo de arquivo diferente do escolhido ou arquivo já importado.
class _DecideStep extends StatelessWidget {
  const _DecideStep({
    required this.inspection,
    required this.chosenOwner,
    required this.onImport,
    required this.onOtherFile,
  });

  final Inspection inspection;
  final AccountOwner? chosenOwner;
  final void Function(AccountOwner? owner, {required bool confirmed}) onImport;
  final VoidCallback onOtherFile;

  bool get _ownerQuestion =>
      inspection.needsOwner ||
      inspection.warnings.any(
        (w) =>
            w.code == 'dono_diferente_do_detectado' ||
            w.code == 'sinais_divergentes',
      );

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final institution = inspection.institution;
    final suggested =
        inspection.detectedOwner ?? inspection.knownOwner ?? chosenOwner;
    final other = suggested == AccountOwner.business
        ? AccountOwner.personal
        : AccountOwner.business;
    final fallbackOwner = chosenOwner ?? suggested;
    final title = inspection.attention.isEmpty
        ? 'Essa conta é pessoal ou da empresa?'
        : 'Confira antes de importar';
    return _StepLayout(
      title: title,
      subtitle: inspection.attention.isEmpty
          ? 'O arquivo não diz isso. Escolha uma vez e o app lembra.'
          : null,
      children: [
        if (inspection.institutionLabel != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Row(
              children: [
                Icon(Icons.verified_rounded, color: c.accent),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Detectei: ${inspection.institutionLabel}'
                    '${inspection.kindLabel == null ? '' : ', ${inspection.kindLabel}'}',
                  ),
                ),
              ],
            ),
          ),
        for (final warning in inspection.attention)
          Container(
            margin: const EdgeInsets.only(bottom: 10),
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: warning.isConflict
                  ? AppTheme.negative.withValues(alpha: 0.10)
                  : c.tint,
              borderRadius: BorderRadius.circular(14),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  warning.isConflict
                      ? Icons.error_outline_rounded
                      : Icons.warning_amber_rounded,
                  semanticLabel: warning.isConflict ? 'Conflito' : 'Atenção',
                  color: warning.isConflict ? AppTheme.negative : c.muted,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    warning.message,
                    style: const TextStyle(height: 1.4),
                  ),
                ),
              ],
            ),
          ),
        if (inspection.signals.isNotEmpty && _ownerQuestion)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              'Como descobri: ${inspection.signals.join('; ')}.',
              style: TextStyle(color: c.muted, fontSize: 13),
            ),
          ),
      ],
      actions: [
        if (_ownerQuestion) ...[
          FilledButton(
            onPressed: () =>
                onImport(suggested ?? AccountOwner.personal, confirmed: true),
            child: Text(
              'Importar como ${ownerLabel(suggested ?? AccountOwner.personal, institution)}',
            ),
          ),
          OutlinedButton(
            onPressed: () => onImport(
              suggested == null ? AccountOwner.business : other,
              confirmed: true,
            ),
            child: Text(
              'Importar como ${ownerLabel(suggested == null ? AccountOwner.business : other, institution)}',
            ),
          ),
        ] else
          FilledButton(
            onPressed: () => onImport(fallbackOwner, confirmed: true),
            child: const Text('Importar mesmo assim'),
          ),
        TextButton(
          onPressed: onOtherFile,
          child: const Text('Escolher outro arquivo'),
        ),
      ],
    );
  }
}

class _SummaryStep extends StatelessWidget {
  const _SummaryStep({
    required this.result,
    required this.statement,
    required this.note,
    required this.onStatementChanged,
    required this.onDone,
  });

  final ImportResult result;
  final StatementInfo? statement;
  final String? note;
  final void Function(StatementInfo statement, String note) onStatementChanged;
  final VoidCallback onDone;

  String _plural(int n, String one, String many) => '$n ${n == 1 ? one : many}';

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final detected = result.institutionLabel == null
        ? null
        : 'Detectei: ${result.institutionLabel}'
              '${result.kindLabel == null ? '' : ', ${result.kindLabel}'}';
    final outcome = switch (result.outcome) {
      'atualizado' =>
        'Atualizei o arquivo deste período'
            '${result.delta == 0 ? '' : ' (${result.delta > 0 ? '+' : ''}${_plural(result.delta, 'lançamento', 'lançamentos')})'}.',
      'repetido' => 'Este arquivo já estava importado: nada mudou.',
      _ => null,
    };
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
        if (result.account != null)
          _SummaryLine(
            icon: Icons.account_balance_wallet_outlined,
            text: 'Conta: ${result.account!.displayLabel}',
          ),
        if (outcome != null)
          _SummaryLine(icon: Icons.update_rounded, text: outcome),
        _SummaryLine(
          icon: Icons.receipt_long_rounded,
          text: _plural(
            result.importedCount,
            'lançamento lido',
            'lançamentos lidos',
          ),
        ),
        if (result.reconciled == true)
          const _SummaryLine(
            icon: Icons.fact_check_outlined,
            text: 'O total da fatura bate com a soma dos lançamentos.',
          ),
        if (result.reconciled == false)
          const _SummaryLine(
            icon: Icons.rule_rounded,
            text:
                'O total da fatura não bate com a soma dos lançamentos: '
                'confira se o PDF está completo.',
          ),
        if (result.duplicateCount > 0 && result.outcome != 'repetido')
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
        if (result.uncategorizedCount > 0) ...[
          _SummaryLine(
            icon: Icons.category_outlined,
            text:
                '${_plural(result.uncategorizedCount, 'gasto sem categoria', 'gastos sem categoria')}'
                ' (aparecem como "Outros" no Resumo)',
          ),
          Align(
            alignment: Alignment.centerLeft,
            child: Padding(
              padding: const EdgeInsets.only(left: 28),
              child: TextButton(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => const CategoryReviewScreen(),
                  ),
                ),
                child: const Text('Categorizar agora'),
              ),
            ),
          ),
        ],
        if (result.autoTransfers > 0)
          _SummaryLine(
            icon: Icons.sync_alt_rounded,
            text:
                'Reconheci ${_plural(result.autoTransfers, 'transferência', 'transferências')}'
                ' entre suas contas e deixei fora dos totais.',
          ),
        if (statement != null)
          _StatementCard(
            statement: statement!,
            note: note,
            onChanged: onStatementChanged,
          ),
        if (result.transferSuggestions > 0)
          Container(
            margin: const EdgeInsets.only(top: 8),
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: c.tint,
              borderRadius: BorderRadius.circular(14),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Encontrei ${_plural(result.transferSuggestions, 'possível transferência', 'possíveis transferências')}'
                  ' entre suas contas (ou pagamento de fatura).',
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 8),
                OutlinedButton(
                  onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => const TransfersScreen(),
                    ),
                  ),
                  child: const Text('Revisar agora'),
                ),
              ],
            ),
          ),
      ],
      actions: [FilledButton(onPressed: onDone, child: const Text('Concluir'))],
    );
  }
}

/// Situação do período do arquivo (fatura aberta ou fechada, extrato parcial), com a pergunta
/// ao usuário quando o app não tem certeza.
class _StatementCard extends StatelessWidget {
  const _StatementCard({
    required this.statement,
    required this.note,
    required this.onChanged,
  });

  final StatementInfo statement;
  final String? note;
  final void Function(StatementInfo statement, String note) onChanged;

  String get _noun => statement.isCard ? 'fatura' : 'extrato';
  String get _this => statement.isCard ? 'esta' : 'este';

  String get _period {
    final start = statement.periodStart;
    final end = statement.periodEnd;
    if (start == null || end == null) return '';
    return '${fullDate(start)} a ${fullDate(end)}';
  }

  String get _question => switch (statement.status) {
    StatementStatus.open =>
      'Esta fatura ainda está aberta'
          '${statement.closesOn == null ? '' : ' e fecha em ${fullDate(statement.closesOn!)}'}'
          '${statement.coveredUntil == null ? '' : ' (os lançamentos vão até ${shortDate(statement.coveredUntil!)})'}.'
          ' Ela já fechou?',
    StatementStatus.partial =>
      'Este extrato ainda não terminou o período'
          '${statement.closesOn == null ? '' : ' (vai até ${fullDate(statement.closesOn!)})'}.'
          ' Ele já está completo?',
    _ =>
      'Não consegui saber se $_this $_noun está completo ($_period). '
          'Ele está completo?',
  };

  Future<void> _answer(BuildContext context, {required bool closed}) async {
    final finance = FinanceScope.of(context);
    try {
      final updated = await finance.confirmStatementClosed(
        statement,
        closed: closed,
      );
      onChanged(
        updated,
        closed
            ? 'Anotado: $_this $_noun está completo.'
            : 'Anotado: $_this $_noun ainda está em andamento. '
                  'Importe de novo quando fechar para atualizar.',
      );
    } on Object {
      if (!context.mounted) return;
      _snack(context, 'Não foi possível salvar. Tente novamente.');
    }
  }

  Future<void> _configure(BuildContext context) async {
    final finance = FinanceScope.of(context);
    final now = DateTime.now();
    final range = await showDateRangePicker(
      context: context,
      firstDate: DateTime(2000),
      lastDate: DateTime(now.year + 2, 12, 31),
      initialDateRange:
          statement.periodStart != null && statement.periodEnd != null
          ? DateTimeRange(
              start: statement.periodStart!,
              end: statement.periodEnd!,
            )
          : null,
      helpText: 'Período do arquivo',
      saveText: 'Salvar',
    );
    if (range == null) return;
    try {
      final updated = await finance.setStatementPeriod(
        statement,
        range.start,
        range.end,
      );
      onChanged(
        updated,
        'Período ajustado: ${fullDate(range.start)} a ${fullDate(range.end)}.',
      );
    } on Object {
      if (!context.mounted) return;
      _snack(context, 'Não foi possível ajustar o período.');
    }
  }

  void _snack(BuildContext context, String message) =>
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(message)));

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final needsAnswer =
        !statement.userConfirmed &&
        (statement.status.isIncomplete ||
            statement.status == StatementStatus.unknown);
    final settled = note != null || statement.userConfirmed;
    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: c.tint,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                statement.status == StatementStatus.closed
                    ? Icons.lock_clock_rounded
                    : Icons.hourglass_top_rounded,
                color: c.accent,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(switch (statement.status) {
                  StatementStatus.closed =>
                    '${statement.isCard ? 'Fatura fechada' : 'Período completo'}'
                        '${_period.isEmpty ? '' : ' · $_period'}',
                  StatementStatus.open =>
                    'Fatura aberta${_period.isEmpty ? '' : ' · $_period'}',
                  StatementStatus.partial =>
                    'Extrato parcial${_period.isEmpty ? '' : ' · $_period'}',
                  StatementStatus.unknown =>
                    'Período${_period.isEmpty ? ' desconhecido' : ' · $_period'}',
                }, style: const TextStyle(fontWeight: FontWeight.w800)),
              ),
            ],
          ),
          if (note != null) ...[
            const SizedBox(height: 8),
            Text(note!, style: const TextStyle(height: 1.4)),
          ] else if (needsAnswer) ...[
            const SizedBox(height: 8),
            Text(_question, style: const TextStyle(height: 1.4)),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilledButton(
                  onPressed: () => _answer(context, closed: true),
                  child: Text(statement.isCard ? 'Já fechou' : 'Está completo'),
                ),
                OutlinedButton(
                  onPressed: () => _answer(context, closed: false),
                  child: Text(
                    statement.isCard ? 'Ainda está aberta' : 'Ainda não',
                  ),
                ),
              ],
            ),
          ],
          if (settled || needsAnswer)
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton(
                onPressed: () => _configure(context),
                child: const Text('Configurar período'),
              ),
            ),
        ],
      ),
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
