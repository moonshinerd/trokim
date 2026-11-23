import 'package:file_picker/file_picker.dart';
import 'package:material_ui/material_ui.dart';

import '../../../core/settings/settings_controller.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/app_motion.dart';
import '../../../core/widgets/screen_header.dart';
import '../../documents/presentation/document_import_button.dart';
import '../../finance/domain/finance_models.dart';
import '../../finance/domain/library_models.dart';
import '../../finance/presentation/finance_controller.dart';
import '../../import_guide/presentation/import_flow_screen.dart';
import 'statement_widgets.dart';

/// Arquivo escolhido pelo usuário, com leitura adiada dos bytes.
class PickedStatement {
  const PickedStatement(this.name, this.readBytes);

  final String name;
  final Future<List<int>> Function() readBytes;
}

typedef StatementPicker = Future<PickedStatement?> Function();

/// Abre o seletor de arquivos do sistema.
///
/// Não filtra por extensão: o Android não conhece o tipo de `.ofx` e deixa o
/// arquivo desabilitado no seletor. A extensão é validada depois da escolha
/// (`FinanceController.importStatement`), com uma mensagem clara.
Future<PickedStatement?> pickStatementFile() async {
  final file = await FilePicker.pickFile(
    dialogTitle: 'Escolha um extrato OFX ou uma fatura PDF',
  );
  if (file == null) return null;
  return PickedStatement(file.name, file.readAsBytes);
}

class TransactionsScreen extends StatelessWidget {
  const TransactionsScreen({super.key, this.pickFile});

  /// Troca o seletor de arquivos (testes).
  final StatementPicker? pickFile;

  /// Abre o fluxo guiado de importação. Com o tutorial desligado em Ajustes,
  /// o fluxo já abre o seletor de arquivos.
  Future<void> _import(BuildContext context) async {
    final finance = FinanceScope.of(context);
    if (finance.importing) return;
    final tutorial = SettingsScope.maybeOf(context)?.showImportTutorial ?? true;
    await Navigator.of(context).push(
      MaterialPageRoute<ImportResult?>(
        builder: (_) =>
            ImportFlowScreen(pickFile: pickFile, startAtPicker: !tutorial),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final finance = FinanceScope.of(context);
    final files = finance.files;
    return Scaffold(
      floatingActionButton: Reveal(
        index: 5,
        child: FloatingActionButton.extended(
          onPressed: finance.importing ? null : () => _import(context),
          backgroundColor: AppTheme.gold,
          foregroundColor: AppTheme.forest,
          elevation: 2,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
          ),
          icon: finance.importing
              ? const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2.5),
                )
              : const Icon(Icons.add_rounded),
          label: Text(
            finance.importing ? 'Importando…' : 'Importar extrato',
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
        ),
      ),
      body: SafeArea(
        bottom: false,
        child: ListView(
          padding: const EdgeInsets.only(bottom: 110),
          children: [
            const Reveal(
              child: ScreenHeader(
                title: 'Extratos e faturas',
                subtitle:
                    'Arquivos que você importou. Nada sai do seu aparelho.',
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
              child: Reveal(
                index: 1,
                child: _PrivacyBanner(onImport: () => _import(context)),
              ),
            ),
            const CoverageNotice(),
            const ShortcutsSection(),
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 20),
              child: DocumentImportButton(),
            ),
            const Padding(
              padding: EdgeInsets.fromLTRB(20, 20, 20, 10),
              child: Reveal(
                index: 2,
                child: Text(
                  'Importados',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
                ),
              ),
            ),
            if (files.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Reveal(
                  index: 3,
                  child: Text(
                    finance.status == FinanceStatus.error
                        ? 'Sem conexão com a API local. Confira o endereço em '
                              'Ajustes.'
                        : 'Nenhum arquivo importado ainda.',
                    style: TextStyle(color: context.colors.muted),
                  ),
                ),
              ),
            for (var i = 0; i < files.length; i++)
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 10),
                child: Reveal(
                  index: 3 + i,
                  child: _FileTile(
                    icon: files[i].kind == 'PDF'
                        ? Icons.credit_card_rounded
                        : Icons.account_balance_rounded,
                    color: files[i].kind == 'PDF'
                        ? AppTheme.negative
                        : context.colors.accent,
                    name: files[i].name,
                    detail: _detail(files[i]),
                    badge: files[i].kind,
                    statement: finance.statements.byFilename(files[i].name),
                    account:
                        finance.statements.byFilename(files[i].name) == null
                        ? null
                        : accountLine(
                            finance.statements,
                            finance.statements.byFilename(files[i].name)!,
                            finance.accounts,
                          ),
                  ),
                ),
              ),
            const AccountsSection(),
          ],
        ),
      ),
    );
  }
}

String _plural(int n, String one, String many) => '$n ${n == 1 ? one : many}';

String _detail(ImportedFile file) {
  final imported = _plural(
    file.imported,
    'transação importada',
    'transações importadas',
  );
  final dup = file.duplicates == 0
      ? 'sem duplicatas'
      : _plural(file.duplicates, 'duplicata evitada', 'duplicatas evitadas');
  return '$imported • $dup';
}

class _PrivacyBanner extends StatelessWidget {
  const _PrivacyBanner({required this.onImport});
  final VoidCallback onImport;

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onTap: onImport,
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: context.colors.tint,
          borderRadius: BorderRadius.circular(24),
        ),
        child: Row(
          children: [
            Container(
              width: 52,
              height: 52,
              decoration: BoxDecoration(
                color: context.colors.surface,
                borderRadius: BorderRadius.circular(18),
              ),
              child: Icon(
                Icons.lock_rounded,
                color: context.colors.accent,
                size: 26,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Processamento 100% local',
                    style: TextStyle(
                      fontWeight: FontWeight.w800,
                      fontSize: 15,
                      color: context.colors.ink,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Aceita OFX e faturas em PDF. O arquivo é lido pela API na sua máquina '
                    'e os lançamentos ficam na memória dela até ser reiniciada.',
                    style: TextStyle(
                      fontSize: 13,
                      height: 1.4,
                      color: context.colors.ink,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _FileTile extends StatelessWidget {
  const _FileTile({
    required this.icon,
    required this.color,
    required this.name,
    required this.detail,
    required this.badge,
    this.statement,
    this.account,
  });

  final IconData icon;
  final Color color;
  final String name;
  final String detail;
  final String badge;
  final StatementInfo? statement;
  final String? account;

  @override
  Widget build(BuildContext context) {
    final tile = Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.colors.surface,
        borderRadius: BorderRadius.circular(AppTheme.radius),
        border: Border.all(color: context.colors.line),
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(icon, color: color, size: 22),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 3),
                if (account != null && account!.isNotEmpty)
                  Text(
                    account!,
                    style: TextStyle(color: context.colors.ink, fontSize: 12),
                  ),
                if (statement != null)
                  Text(
                    statementLine(statement!),
                    style: TextStyle(color: context.colors.muted, fontSize: 12),
                  ),
                Text(
                  detail,
                  style: TextStyle(color: context.colors.muted, fontSize: 12),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 5,
                ),
                decoration: BoxDecoration(
                  color: context.colors.bg,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  badge,
                  style: const TextStyle(
                    fontWeight: FontWeight.w800,
                    fontSize: 11,
                    letterSpacing: 0.5,
                  ),
                ),
              ),
              if (statement != null) ...[
                const SizedBox(height: 6),
                StatusPill(statement: statement!),
              ],
            ],
          ),
        ],
      ),
    );
    if (statement == null) return tile;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(AppTheme.radius),
        onTap: () => showStatementSheet(context, statement!),
        child: tile,
      ),
    );
  }
}
